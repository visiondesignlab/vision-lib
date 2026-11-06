import {DurableObject} from 'cloudflare:workers';
import catalog from '../static/playground/catalog.json';
import {setCatalog,validatePlane} from '../static/playground/protocol.js';
import {toPlatform} from '../static/playground/mapper.js';
setCatalog(catalog.models);
const API='https://api.higgsfield.ai';
const TYPES=new Set(['image/jpeg','image/png','image/webp','image/gif','video/mp4','video/quicktime','audio/wav','audio/x-wav','audio/mpeg']);
const response=(value,status=200,headers={})=>Response.json(value,{status,headers:{'Cache-Control':'no-store',...headers}});
async function body(request){
  if(request.headers.get('Content-Type')?.split(';')[0]!=='application/json')throw Error('需要 JSON 请求');
  const reader=request.body?.getReader();if(!reader)throw Error('请求为空');
  let size=0,text='',decoder=new TextDecoder();
  for(;;){const {value,done}=await reader.read();if(done)break;size+=value.byteLength;if(size>262144){await reader.cancel();throw Error('请求过大');}text+=decoder.decode(value,{stream:true});}
  return JSON.parse(text+decoder.decode());
}
async function upstream(key,path,payload){
  const headers={Authorization:'Key '+key};if(payload)headers['Content-Type']='application/json';
  let result;
  try{result=await fetch(API+path,{method:payload?'POST':'GET',headers,body:payload?JSON.stringify(payload):undefined,redirect:'manual',signal:AbortSignal.timeout(25000)});}
  catch{throw Error(payload?'服务连接中断，提交结果未确认。请先在 Higgsfield 核对，避免重复生成。':'状态读取失败，请稍后重试');}
  if(result.status>=300&&result.status<400)throw Error('生成服务返回了跳转地址，已停止转发，请稍后重试');
  let data;try{data=await result.json();}catch{throw Error('生成服务返回了无法读取的结果');}
  if(!result.ok){
    const message={401:'API Key 无效或已失效，请重新连接',403:'当前 API Key 没有此模型的权限',402:'Higgsfield 额度不足，请在原站充值',429:'请求较多，请稍后重试'}[result.status];
    const detail=typeof data.detail==='string'?data.detail.replaceAll(key,'[已隐藏]'):'';
    throw Error(message||`生成服务返回 ${result.status}${detail?'：'+detail.slice(0,240):'，请检查模型和参数'}`);
  }
  return data;
}
// Each visitor owns a server-side session. Credentials never appear in the returned token or logs.
export class GenerationSession extends DurableObject {
  async alarm(){await this.ctx.storage.deleteAll();}
  async fetch(request){
    const route=new URL(request.url).pathname;
    try{
      if(route==='/connect'){
        const {key}=await body(request),expires=Date.now()+12*3600000;
        await this.ctx.storage.put({key,expires});await this.ctx.storage.setAlarm(expires);
        return response({configured:true,expires});
      }
      const stored=await this.ctx.storage.get(['key','expires']),key=stored.get('key');
      if(!key||stored.get('expires')<Date.now())return response({error:'连接已过期，请重新连接 API Key',code:'connection_expired'},401);
      if(route==='/connection')return response({configured:true,expires:stored.get('expires')});
      if(route==='/disconnect'){await this.ctx.storage.deleteAll();return response({configured:false});}
      const input=await body(request);
      if(route==='/generate'){
        const plane=validatePlane(input.plane),id=input.clientId;
        if(typeof id!=='string'||! /^[a-z0-9-]{20,80}$/i.test(id))return response({error:'无效的提交标识'},400);
        const record='submission:'+id;
        // Storage writes precede network calls, preventing duplicate submissions on concurrent requests.
        const existing=await this.ctx.storage.transaction(async tx=>{const old=await tx.get(record);if(!old)await tx.put(record,{error:'这个请求正在提交或结果尚未确认，请先检查原站',pending:true});return old;});
        if(existing)return response(existing,existing.error?409:200);
        const mapped=toPlatform(plane);
        try{
          const data=await upstream(key,'/'+mapped.path,mapped.body);
          if(typeof data.request_id!=='string'||!data.request_id)throw Error('服务未返回任务编号，请在原站核对');
          const result={requestId:data.request_id,status:data.status||'queued'};
          await this.ctx.storage.put({[record]:result,['job:'+data.request_id]:true});
          return response(result,201);
        }catch(error){const result={error:error.message};await this.ctx.storage.put(record,result);return response(result,502);}
      }
      if(route==='/status'||route==='/cancel'){
        const ids=route==='/cancel'?[input.requestId]:input.ids;
        if(!Array.isArray(ids)||ids.length<1||ids.length>12||ids.some(id=>typeof id!=='string'||! /^[\w-]{1,150}$/.test(id)))throw Error('无效的任务编号');
        const owns=await this.ctx.storage.get(ids.map(id=>'job:'+id));
        if(ids.some(id=>!owns.get('job:'+id)))return response({error:'任务不属于当前连接，无法查询或取消'},403);
        if(route==='/cancel')return response(await upstream(key,'/requests/'+ids[0]+'/cancel',{}));
        return response({results:await Promise.all(ids.map(async id=>{try{return {requestId:id,...await upstream(key,'/requests/'+id+'/status')};}catch(error){return {requestId:id,error:error.message};}}))});
      }
      if(route==='/upload'){
        if(!TYPES.has(input.contentType))throw Error('暂不支持这种文件格式');
        return response(await upstream(key,'/files/generate-upload-url',{content_type:input.contentType}));
      }
      return response({error:'入口不存在'},404);
    }catch(error){return response({error:error.message||'请求失败'},400);}
  }
}
export default {
  async fetch(request,env){
    const origin=request.headers.get('Origin'),route=new URL(request.url).pathname;
    const allowed=new Set([env.SITE_ORIGIN,'http://127.0.0.1:8787','http://localhost:8787','http://127.0.0.1:8792','http://127.0.0.1:8794']);
    if(!origin||!allowed.has(origin))return response({error:'请求来源无效'},403);
    const cors={'Access-Control-Allow-Origin':origin,'Vary':'Origin','Access-Control-Allow-Methods':'GET, POST, OPTIONS','Access-Control-Allow-Headers':'Content-Type, Authorization','Access-Control-Max-Age':'600'};
    if(request.method==='OPTIONS')return new Response(null,{status:204,headers:cors});
    if(route==='/health'&&request.method==='GET')return response({ok:true,models:catalog.models.length},200,cors);
    if(!['/connect','/connection','/disconnect','/generate','/status','/cancel','/upload'].includes(route))return response({error:'入口不存在'},404,cors);
    if(request.method!==(route==='/connection'?'GET':'POST'))return response({error:'请求方法无效'},405,cors);
    try{
      let token=request.headers.get('Authorization')?.replace(/^Bearer /,'');
      if(route==='/connect'){
        const input=await body(request),key=input.key?.trim();
        if(typeof key!=='string'||key.length<8||key.length>2048||/[\s\x00-\x1f]/.test(key))throw Error('请粘贴完整 API Key');
        token=crypto.randomUUID()+crypto.randomUUID();
        const session=env.SESSIONS.get(env.SESSIONS.idFromName(token));
        const result=await session.fetch(new Request('https://session/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})}));
        return response({...await result.json(),token},result.status,cors);
      }
      if(!token||! /^[a-f0-9-]{72}$/.test(token))return response({error:'请先连接 API Key',code:'connection_expired'},401,cors);
      const session=env.SESSIONS.get(env.SESSIONS.idFromName(token));
      const result=await session.fetch(new Request('https://session'+route,request));
      const headers=new Headers(result.headers);for(const [key,value] of Object.entries(cors))headers.set(key,value);
      return new Response(result.body,{status:result.status,headers});
    }catch(error){return response({error:error.message||'请求格式无效'},400,cors);}
  }
};

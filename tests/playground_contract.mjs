import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {setCatalog,validatePlane} from '../static/playground/protocol.js';
import {toPlatform} from '../static/playground/mapper.js';
const catalog=JSON.parse(await readFile(new URL('../static/playground/catalog.json',import.meta.url)));
setCatalog(catalog.models);
const plane=(model='soul-2',media={},settings={})=>({model,prompt:{text:'A clean product photograph'},media,settings});
const media=role=>({[role]:[{url:'https://example.org/reference.png'}]});
test('all 38 installed models map to their configured endpoints',()=>{
 assert.equal(catalog.models.length,38);assert.equal(catalog.models.filter(m=>m.surface==='image').length,8);
 for(const model of catalog.models){
  const inputs={};for(const role of Object.keys(model.roles))inputs[role]=[{url:'https://example.org/reference.png'}];
  const mapped=toPlatform(validatePlane(plane(model.id,inputs)));
  assert.match(mapped.path,/^[a-z0-9][a-z0-9./-]+$/);assert.equal(mapped.body.prompt,'A clean product photograph');
 }
});
test('model operations preserve distinct first frame, reference, edit and motion mappings',()=>{
 assert.equal(toPlatform(validatePlane(plane('seedance-2.5'))).path,'bytedance/seedance-2.5/text-to-video');
 assert.equal(toPlatform(validatePlane(plane('seedance-2.5',media('start')))).path,'bytedance/seedance-2.5/image-to-video');
 assert.equal(toPlatform(validatePlane(plane('seedance-2.5',media('reference')))).path,'bytedance/seedance-2.5/reference-to-video');
 assert.equal(toPlatform(validatePlane(plane('seedance-2.5-edit',media('video')))).body.video_url,'https://example.org/reference.png');
 assert.equal(toPlatform(validatePlane(plane('kling-3-pro',{...media('start'),...media('end')}))).body.last_image_url,'https://example.org/reference.png');
});
test('validation rejects impossible settings, unsupported media and incomplete operations',()=>{
 for(const p of [plane('missing'),plane('soul-2',media('start')),plane('seedance-2.5',{}, {duration:NaN}),plane('seedance-2.5',{}, {duration:4.5}),plane('seedance-2.5-edit'),plane('kling-3-motion-std',media('start')),plane('seedance-2.5',media('end')),plane('flux-2',{reference:[{url:'http://127.0.0.1/a.png'}]})])assert.throws(()=>validatePlane(p));
});
// Exercise the service with isolated storage and a deterministic provider; never spend real credits.
class MemoryStorage{
 data=new Map();queue=Promise.resolve();
 async get(key){return Array.isArray(key)?new Map(key.filter(k=>this.data.has(k)).map(k=>[k,this.data.get(k)])):this.data.get(key);}
 async put(key,value){if(typeof key==='object')for(const [k,v] of Object.entries(key))this.data.set(k,v);else this.data.set(key,value);}
 async transaction(fn){const result=this.queue.then(()=>fn(this));this.queue=result.catch(()=>{});return result;}
 async setAlarm(){}async deleteAll(){this.data.clear();}
}
let code=await readFile(new URL('../playground-service/worker.js',import.meta.url),'utf8');
code=code.replace("import {DurableObject} from 'cloudflare:workers';","class DurableObject {constructor(ctx){this.ctx=ctx;}}")
 .replace("import catalog from '../static/playground/catalog.json';",'const catalog='+JSON.stringify(catalog)+';')
 .replaceAll("'../static/playground/protocol.js'",JSON.stringify(new URL('../static/playground/protocol.js',import.meta.url).href))
 .replaceAll("'../static/playground/mapper.js'",JSON.stringify(new URL('../static/playground/mapper.js',import.meta.url).href));
const {default:worker,GenerationSession}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const sessions=new Map(),env={SITE_ORIGIN:'https://visiondesignlab.github.io',SESSIONS:{idFromName:id=>id,get(id){if(!sessions.has(id))sessions.set(id,new GenerationSession({storage:new MemoryStorage()}));return sessions.get(id);}}};
async function send(path,data,token,origin='http://127.0.0.1:8787'){
 const headers={Origin:origin};if(data)headers['Content-Type']='application/json';if(token)headers.Authorization='Bearer '+token;
 const response=await worker.fetch(new Request('https://service.test'+path,{method:data?'POST':'GET',headers,body:data?JSON.stringify(data):undefined}),env);
 return {status:response.status,data:await response.json(),response};
}
test('generation service isolates credentials and jobs, deduplicates submissions, uploads and disconnects',async()=>{
 let calls=0;const original=globalThis.fetch;
 globalThis.fetch=async(url,options)=>{
  assert.equal(options.headers.Authorization,'Key test-key-private');
  assert.equal(options.redirect,'manual');
  assert.ok(url.startsWith('https://api.higgsfield.ai/'));
  if(url.endsWith('/generate-upload-url'))return Response.json({upload_url:'https://storage.example.org/signed',public_url:'https://storage.example.org/file.png',upload_headers:{'Content-Type':'image/png'}});
  if(url.endsWith('/status'))return Response.json({request_id:'test-job',status:'completed',images:[{url:'https://example.org/result.png'}]});
  if(url.endsWith('/cancel'))return Response.json({status:'canceled'});
  calls++;assert.equal(JSON.parse(options.body).prompt,'A clean product photograph');return Response.json({request_id:'test-job',status:'queued'});
 };
 try{
  assert.equal((await send('/connect',{key:'test-key-private'},null,'https://attacker.example')).status,403);
  const connection=await send('/connect',{key:'test-key-private'}),token=connection.data.token;
  assert.equal(connection.status,200);assert.equal(JSON.stringify(connection.data).includes('test-key-private'),false);
  const input={plane:plane(),clientId:crypto.randomUUID()};
  const two=await Promise.all([send('/generate',input,token),send('/generate',input,token)]);assert.equal(calls,1);assert.ok(two.some(r=>r.status===201));
  assert.equal((await send('/generate',{...input,clientId:crypto.randomUUID(),plane:plane('bogus')},token)).status,400);
  const other=(await send('/connect',{key:'another-private-key'})).data.token;
  assert.equal((await send('/status',{ids:['test-job']},other)).status,403);
  const result=await send('/status',{ids:['test-job']},token);assert.equal(result.data.results[0].status,'completed');
  assert.equal((await send('/cancel',{requestId:'test-job'},token)).data.status,'canceled');
  assert.equal((await send('/upload',{contentType:'text/html'},token)).status,400);
  assert.equal((await send('/upload',{contentType:'image/png'},token)).data.public_url,'https://storage.example.org/file.png');
  assert.equal((await send('/disconnect',{},token)).status,200);
  assert.equal((await send('/connection',undefined,token)).status,401);
 }finally{globalThis.fetch=original;}
});

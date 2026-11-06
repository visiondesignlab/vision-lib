let base='',token='';
try{token=sessionStorage.getItem('vision-playground-session')||'';}catch{}
export function configure(url){base=url.replace(/\/$/,'');}
export function connected(){return !!token;}
function remember(value){token=value;try{value?sessionStorage.setItem('vision-playground-session',value):sessionStorage.removeItem('vision-playground-session');}catch{}}
export async function request(path,body){
  if(!base){
    try{const r=await fetch(window.VisionSite.path('/static/playground/config.json'),{cache:'no-store'});if(r.ok)configure((await r.json()).apiUrl||'');}catch{}
  }
  if(!base)throw Error('生成服务尚未配置，请稍后再试');
  const headers={};if(token)headers.Authorization='Bearer '+token;if(body)headers['Content-Type']='application/json';
  let r;try{r=await fetch(base+path,{method:body?'POST':'GET',headers,body:body?JSON.stringify(body):undefined,credentials:'omit',signal:AbortSignal.timeout(35000)});}catch{throw Error(path==='/generate'?'提交结果未确认，请先在 Higgsfield 核对，避免重复生成。':'服务连接失败，请检查网络后重试');}
  let data;try{data=await r.json();}catch{throw Error('服务响应异常，请稍后重试');}
  if(r.status===401&&data.code==='connection_expired')remember('');
  if(!r.ok)throw Error(data.error||'请求失败');
  return data;
}
export async function connect(key){const data=await request('/connect',{key});remember(data.token);return data;}
export async function disconnect(){await request('/disconnect',{});remember('');}

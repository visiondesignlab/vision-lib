import {setCatalog,getModel,validatePlane,publicURL,roleNames,settingNames} from './protocol.js';
import {toPlatform} from './mapper.js';
import * as storage from './storage.js';
import * as api from './api.js';
const {path:sitePath,icon}=window.VisionSite;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const uid=()=>crypto.randomUUID();
const active=r=>['submitting','queued','in_progress','running','processing'].includes(r.status);
const names={submitting:'正在提交',queued:'排队中',in_progress:'正在生成',running:'正在生成',processing:'正在生成',completed:'已完成',failed:'生成失败',nsfw:'未通过内容审核',canceled:'已取消',paused:'查询已暂停'};
const starterPrompts={image:[['产品摄影','白色无线耳机置于浅灰色背景，柔和的自然侧光，精细金属与塑料质感，极简产品摄影，保留充足留白。'],['品牌海报','为一款智能耳机创作极简品牌海报，抽象声波与干净几何构成，黑白配色，清晰的视觉焦点，无文字。'],['空间概念','一间面向山林的现代工作室，落地窗，木质家具，温暖日光，建筑摄影，安静而真实。']],video:[['产品运镜','镜头缓慢环绕桌面上的白色无线耳机，从侧面移动到正面，柔和自然光，稳定运镜，精细材质，电影级产品广告。'],['自然光影','清晨阳光穿过树叶，在白色墙面上留下缓慢移动的光影，静态镜头，自然风，安静的氛围。'],['城市街景','傍晚的城市街道，镜头平稳向前推进，玻璃幕墙映出夕阳，行人自然经过，真实电影摄影。']]};
function kindFor(role){return role==='video'?'video':role==='audio'?'audio':'image';}
function options(model){return Object.fromEntries(Object.entries(model.settings).map(([k,v])=>[k,v.default]));}
function shortDate(t){return new Intl.DateTimeFormat('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(t);}
export async function createPlayground({notify}){
  const [catalog,config]=await Promise.all(['catalog.json','config.json'].map(async file=>{const r=await fetch(sitePath('/static/playground/'+file));if(!r.ok)throw Error('工具加载失败');return r.json();}));
  setCatalog(catalog.models);api.configure(config.apiUrl);
  const view=document.createElement('div');view.className='playground';
  let records=[],uploads=[],draft={},storageWarning='';
  try{[records,uploads,draft]=await Promise.all([storage.read('history',[]),storage.read('uploads',[]),storage.read('draft',{})]);}catch{storageWarning='浏览器存储不可用，本次结果仅在当前页面保留，请及时下载。';}
  records=records.map(r=>r.status==='submitting'?{...r,status:'failed',error:'页面在提交时关闭，结果尚未确认。请先在原站核对，再决定是否重新生成。'}:r);
  let surface=draft.surface==='video'?'video':'image',modelId=draft.model||'soul-2';
  if(!catalog.models.some(m=>m.id===modelId))modelId='soul-2';
  surface=getModel(modelId).surface;
  let prompt=draft.prompt||'',settingsByModel=draft.settings||{},media=draft.media||{},batch=1,scope='all',selected=new Set(),selecting=false,busy=false,uploading=false,timer,polling=false,visible=false,dialog,undoTimer,undoRows=[],lastSelection;
  const $=s=>view.querySelector(s);
  const model=()=>getModel(modelId);
  const settings=()=>settingsByModel[modelId]||=(options(model()));
  function save(key,value){return storage.write(key,value).catch(()=>{storageWarning='无法保存到浏览器，请及时下载本次结果。';if($('.pg-history-note'))$('.pg-history-note').textContent=storageWarning;});}
  function saveDraft(){save('draft',{surface,model:modelId,prompt,settings:settingsByModel,media});}
  function saveRecords(){const keep=records.filter(r=>!r.favorite&&!active(r)).slice(0,60);records=records.filter(r=>r.favorite||active(r)||keep.includes(r));return save('history',records);}
  function error(text=''){$('.pg-error').textContent=text;}
  function closeDialog(){if(dialog){dialog.close();dialog.remove();dialog=null;}}
  function openDialog(title,body,wide=false){
    closeDialog();const d=document.createElement('dialog');d.className='pg-dialog'+(wide?' pg-viewer':'');d.setAttribute('aria-labelledby','pg-dialog-title');
    d.innerHTML=`<div class="pg-dialog-head"><h2 id="pg-dialog-title">${esc(title)}</h2><button type="button" class="ibtn" aria-label="关闭">${icon('close')}</button></div>${body}`;
    view.append(d);dialog=d;d.querySelector('.pg-dialog-head button').onclick=closeDialog;d.addEventListener('close',()=>{d.querySelectorAll('video').forEach(v=>v.pause());d.remove();if(dialog===d)dialog=null;});d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeDialog();}});d.showModal();return d;
  }
  function updateConnection(){
    $('.pg-key').innerHTML=icon(api.connected()?'check':'plus')+(api.connected()?'API Key 已配置':'连接 API Key');
    $('.pg-submit').disabled=busy||uploading;
  }
  function connectDialog(){
    const d=openDialog(api.connected()?'管理 API Key':'连接 API Key',`<p>粘贴从 Higgsfield 复制的完整 API Key。服务地址已配置，生成使用你自己的额度。</p><form><label class="pg-field"><span>API Key</span><input type="password" name="key" autocomplete="off" spellcheck="false" required placeholder="粘贴完整 API Key"></label><p class="pg-error" role="alert"></p><div class="pg-dialog-actions"><a href="https://open.higgsfield.ai/api-keys" target="_blank" rel="noopener noreferrer">获取 API Key ${icon('external')}</a>${api.connected()?'<button type="button" class="pill-btn grey pg-disconnect">移除</button>':''}<button class="pill-btn dark" type="submit">${api.connected()?'替换 API Key':'保存 API Key'}</button></div><small class="pg-help">密钥仅保存在生成服务的独立会话中，12 小时后过期；不会写入浏览器历史或公开网站文件。</small></form>`);
    d.querySelector('form').onsubmit=async e=>{e.preventDefault();const input=d.querySelector('input'),submit=d.querySelector('[type=submit]');submit.disabled=true;try{await api.connect(input.value);input.value='';updateConnection();closeDialog();notify('API Key 已保存，可开始生成');schedule();}catch(e){d.querySelector('.pg-error').textContent=e.message;}finally{submit.disabled=false;}};
    d.querySelector('.pg-disconnect')?.addEventListener('click',async e=>{e.target.disabled=true;try{await api.disconnect();clearTimeout(timer);updateConnection();closeDialog();notify('API Key 已移除');}catch(e){d.querySelector('.pg-error').textContent=e.message;}});
  }
  function selectModel(id){modelId=id;surface=model().surface;media={};saveDraft();renderComposer();renderGallery();}
  function modelDialog(){
    const d=openDialog('选择模型',`<label class="pg-field"><span class="pg-help">${surface==='image'?'图像':'视频'}模型 · ${catalog.models.filter(m=>m.surface===surface).length} 个</span><input type="search" placeholder="搜索模型" aria-label="搜索模型"></label><div class="pg-model-list"></div>`);
    const paint=()=>{const query=d.querySelector('input').value.toLowerCase();d.querySelector('.pg-model-list').innerHTML=catalog.models.filter(m=>m.surface===surface&&(m.label+' '+m.id).toLowerCase().includes(query)).map(m=>`<button type="button" class="pg-model-option" data-model="${m.id}" aria-pressed="${m.id===modelId}"><span>${esc(m.label)}<small>${Object.keys(m.roles).length?Object.keys(m.roles).map(r=>roleNames[r]).join(' · '):'文字生成'}</small></span>${m.id===modelId?icon('check'):''}</button>`).join('')||'<p>没有找到这个模型。</p>';d.querySelectorAll('[data-model]').forEach(b=>b.onclick=()=>{selectModel(b.dataset.model);closeDialog();});};d.querySelector('input').oninput=paint;paint();
  }
  function renderComposer(){
    const m=model(),s=settings();
    $('.pg-composer').innerHTML=`<div class="pg-mode" aria-label="生成类型"><button class="chip ${surface==='image'?'on':''}" type="button" data-surface="image">图片</button><button class="chip ${surface==='video'?'on':''}" type="button" data-surface="video">视频</button></div>
      <label class="pg-field"><span>模型</span><button type="button" class="pill-btn shadow pg-model">${esc(m.label)}${icon('caret')}</button></label>
      <label class="pg-field"><span>提示词</span><textarea name="prompt" maxlength="12000" placeholder="描述你想创作的画面、风格与细节…">${esc(prompt)}</textarea></label>
      ${Object.keys(m.roles).length?`<div class="pg-field"><span>参考素材</span><div class="pg-media">${Object.entries(m.roles).map(([role,max])=>`<div><div class="pg-media-head"><button type="button" class="pill-btn shadow" data-add="${role}">${icon('plus')}${roleNames[role]}</button><span>${(media[role]||[]).length} / ${max}</span></div><div class="pg-media-items">${(media[role]||[]).map((item,i)=>`<div class="pg-attachment" title="${esc(item.name||roleNames[role])}">${kindFor(role)==='image'?`<img src="${esc(item.url)}" alt="${roleNames[role]}">`:kindFor(role)==='video'?`<video src="${esc(item.url)}" muted preload="metadata"></video>`:icon('play')}<button type="button" data-remove="${role}:${i}" aria-label="移除${roleNames[role]}">${icon('close')}</button></div>`).join('')}</div></div>`).join('')}</div></div>`:''}
      <div class="pg-settings">${Object.entries(m.settings).map(([key,f])=>f.type==='boolean'?`<label class="pg-toggle"><span>${esc(settingNames[key]||key)}</span><input type="checkbox" data-setting="${key}" ${s[key]?'checked':''}></label>`:`<label class="pg-field"><span class="pg-help">${esc(settingNames[key]||key)}</span>${f.type==='enum'?`<select data-setting="${key}" aria-label="${esc(settingNames[key]||key)}">${f.values.map(v=>`<option value="${esc(v)}" ${s[key]===v?'selected':''}>${esc(v==='auto'?'自动':v==='video'?'视频':v==='image'?'图片':v)}</option>`).join('')}</select>`:`<input type="number" data-setting="${key}" min="${f.min}" max="${f.max}" step="${f.step||1}" value="${s[key]}" aria-label="${esc(settingNames[key]||key)}">`}</label>`).join('')}${!m.settings.batchSize?`<label class="pg-field"><span class="pg-help">生成数量</span><select name="batch" aria-label="生成数量">${[1,2,3,4].map(n=>`<option ${batch===n?'selected':''}>${n}</option>`).join('')}</select></label>`:''}</div>
      <p class="pg-error" role="alert"></p><div class="pg-submit-row"><small>⌘ / Ctrl + Enter</small><button type="submit" class="pill-btn dark pg-submit">${busy?'正在提交…':'生成'} ${icon('forward')}</button></div>`;
    $('.pg-model').onclick=modelDialog;
    $('.pg-composer').querySelectorAll('[data-surface]').forEach(b=>b.onclick=()=>{if(b.dataset.surface!==surface)selectModel(catalog.models.find(m=>m.surface===b.dataset.surface).id);});
    $('textarea').oninput=e=>{prompt=e.target.value;saveDraft();};
    $('textarea').onkeydown=e=>{if((e.metaKey||e.ctrlKey)&&e.key==='Enter'){e.preventDefault();generate();}};
    $('.pg-composer').querySelectorAll('[data-setting]').forEach(input=>{input.onchange=()=>{settings()[input.dataset.setting]=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value;saveDraft();};});
    $('.pg-composer').querySelectorAll('select').forEach(select=>window.VisionMenu.enhanceSelect(select,select.getAttribute('aria-label')));
    $('[name=batch]')?.addEventListener('change',e=>batch=Number(e.target.value));
    $('.pg-composer').querySelectorAll('[data-add]').forEach(b=>b.onclick=()=>assetDialog(b.dataset.add));
    $('.pg-composer').querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{const [r,i]=b.dataset.remove.split(':');media[r].splice(Number(i),1);saveDraft();renderComposer();});
    updateConnection();
  }
  async function generate(){
    if(busy||uploading)return;
    if(!api.connected()){connectDialog();return;}
    let plane;try{plane=validatePlane({model:modelId,prompt:{text:prompt},media,settings:settings()});toPlatform(plane);}catch(e){error(e.message);return;}
    if(records.filter(active).length+(model().settings.batchSize?1:batch)>8){error('最多同时生成 8 个任务，请等待当前任务完成');return;}
    const count=model().settings.batchSize?1:batch;busy=true;error();updateConnection();$('.pg-submit').textContent='正在提交…';
    try{
      await Promise.all(Array.from({length:count},async()=>{
        const record={id:uid(),plane:structuredClone(plane),kind:surface,model:model().label,created:Date.now(),status:'submitting',outputs:[],favorite:false};records.unshift(record);saveRecords();renderGallery();
        try{const result=await api.request('/generate',{plane,clientId:record.id});record.requestId=result.requestId;record.status=result.status==='completed'?'queued':result.status;record.pollStart=Date.now();}
        catch(e){record.status='failed';record.error=e.message;}
        saveRecords();renderGallery();
      }));
    }finally{busy=false;updateConnection();$('.pg-submit').innerHTML='生成 '+icon('forward');schedule();}
  }
  function schedule(){clearTimeout(timer);if(visible&&api.connected()&&records.some(active))timer=setTimeout(poll,4000);}
  async function poll(){
    if(polling||!visible||!api.connected())return;polling=true;
    try{
      const pending=records.filter(r=>active(r)&&r.requestId);
      for(const r of pending){if(Date.now()-(r.pollStart||r.created)>600000){r.status='paused';r.error='等待超过 10 分钟，任务可能仍在运行，可继续查询。';}}
      const current=pending.filter(active).slice(0,12);
      if(current.length){
        const {results}=await api.request('/status',{ids:current.map(r=>r.requestId)});
        for(const result of results){const r=records.find(r=>r.requestId===result.requestId);if(!r)continue;
          if(result.error&&!result.status){r.misses=(r.misses||0)+1;if(r.misses>=3){r.status='paused';r.error=String(result.error);}continue;}
          r.misses=0;r.status=names[result.status]?result.status:'processing';r.error='';
          if(r.status==='completed'){
            r.outputs=[...(result.images||[]).map(i=>({url:publicURL(i.url),kind:'image'})),...(result.video?.url?[{url:publicURL(result.video.url),kind:'video'}]:[])].filter(o=>o.url);
            if(!r.outputs.length){r.status='failed';r.error='服务已完成，但没有返回可用媒体地址，请在原站核对。';}
          }else if(['failed','nsfw','canceled'].includes(r.status))r.error=typeof result.error==='string'?result.error:names[r.status];
        }
      }
      saveRecords();renderGallery();
    }catch(e){for(const r of records.filter(active)){r.misses=(r.misses||0)+1;if(r.misses>=3){r.status='paused';r.error=e.message;}}saveRecords();renderGallery();updateConnection();}
    finally{polling=false;schedule();}
  }
  function galleryRows(){return records.filter(r=>scope==='all'||scope==='favorites'&&r.favorite||r.kind===scope);}
  function mediaHTML(o){return o.kind==='video'?`<video src="${esc(o.url)}" muted playsinline preload="metadata"></video>`:`<img src="${esc(o.url)}" loading="lazy" alt="生成结果">`;}
  function renderGallery(){
    const list=galleryRows();$('.pg-tabs').innerHTML=[['all','全部'],['image','图片'],['video','视频'],['favorites','收藏']].map(([id,name])=>`<button type="button" class="chip ${scope===id?'on':''}" data-scope="${id}">${name}${id==='all'?` <span class="cnt">${records.length}</span>`:''}</button>`).join('');
    $('.pg-tabs').querySelectorAll('button').forEach(b=>b.onclick=()=>{scope=b.dataset.scope;selected.clear();selecting=false;renderGallery();});
    $('.pg-select-toggle').textContent=selecting?'完成':'选择';$('.pg-select-toggle').disabled=!list.length;
    const selection=$('.pg-selection');selection.hidden=!selecting;selection.innerHTML=`<span class="pg-count">已选 ${selected.size} 项</span><button type="button" class="pill-btn grey" data-bulk="all">全选</button><button type="button" class="pill-btn shadow" data-bulk="favorite" ${selected.size?'':'disabled'}>收藏</button><button type="button" class="pill-btn shadow" data-bulk="download" ${selected.size?'':'disabled'}>下载</button><button type="button" class="pill-btn shadow" data-bulk="delete" ${selected.size?'':'disabled'}>删除</button>`;
    selection.querySelectorAll('button').forEach(b=>b.onclick=()=>bulk(b.dataset.bulk));
    const grid=$('.pg-grid');grid.classList.toggle('selecting',selecting);
    grid.innerHTML=list.map(r=>{
      const ratio=r.plane.settings.aspectRatio?.split(':').map(Number),aspect=ratio?.length===2?ratio[0]/ratio[1]:r.kind==='video'?16/9:1;
      return `<article class="pg-card" data-record="${r.id}" data-selected="${selected.has(r.id)}"><div class="pg-card-media" style="--ratio:${aspect}">${r.outputs?.length?`<button type="button" class="pg-preview" aria-label="预览 ${esc(r.model)} 生成结果">${mediaHTML(r.outputs[0])}</button>`:`<div class="pg-state">${icon(active(r)?'time':'image')}<span>${names[r.status]||'等待结果'}</span>${r.error?`<p>${esc(r.error)}</p>`:''}${r.status==='paused'?'<button type="button" class="pill-btn shadow" data-run="resume">继续查询</button>':active(r)?(r.requestId?'<button type="button" class="pill-btn shadow" data-run="cancel">取消任务</button>':''):'<button type="button" class="pill-btn shadow" data-run="reuse">重新编辑</button>'}</div>`}<div class="pg-card-actions"><label title="选择"><input type="checkbox" aria-label="选择 ${esc(r.model)}" ${selected.has(r.id)?'checked':''}></label><button type="button" aria-label="${r.favorite?'取消收藏':'收藏'}" aria-pressed="${!!r.favorite}">${icon('star')}</button></div></div><div class="pg-card-caption"><div><b>${esc(r.model)}${r.outputs?.length>1?' · '+r.outputs.length+' 张':''}</b><p>${esc(r.plane.prompt.text)}</p></div><time>${shortDate(r.created)}</time></div></article>`;
    }).join('');
    $('.pg-empty').hidden=!!list.length;$('.pg-empty').style.display=list.length?'none':'flex';
    $('.pg-empty').innerHTML=`${icon('image')}<h2>${scope==='favorites'?'还没有收藏':records.length?'这里还没有作品':'从一个想法开始'}</h2><p>${scope==='favorites'?'点击作品上的星标，把想保留的结果放到这里。':'描述画面，选择模型。生成结果会保存在当前浏览器，方便继续创作。'}</p>${!records.length?`<div class="pg-starters">${starterPrompts[surface].map(([label],i)=>`<button type="button" class="pill-btn shadow" data-starter="${i}">${label} ${icon('forward')}</button>`).join('')}</div>`:''}`;
    $('.pg-empty').querySelectorAll('[data-starter]').forEach(b=>b.onclick=()=>{prompt=starterPrompts[surface][Number(b.dataset.starter)][1];saveDraft();renderComposer();$('textarea').focus();});
    grid.querySelectorAll('.pg-card').forEach(card=>{
      const r=records.find(r=>r.id===card.dataset.record);
      card.querySelector('.pg-preview')?.addEventListener('click',()=>selecting?toggle(r.id):viewer(r.id));
      card.querySelector('input').onclick=e=>{if(e.shiftKey&&lastSelection){const ids=list.map(r=>r.id),a=ids.indexOf(lastSelection),b=ids.indexOf(r.id);ids.slice(Math.min(a,b),Math.max(a,b)+1).forEach(id=>selected.add(id));selecting=true;renderGallery();}else toggle(r.id);lastSelection=r.id;};
      card.querySelector('.pg-card-actions>button').onclick=()=>{r.favorite=!r.favorite;saveRecords();renderGallery();};
      card.querySelector('[data-run]')?.addEventListener('click',async e=>{const action=e.currentTarget.dataset.run;
        if(action==='reuse')reuse(r);else if(action==='resume'){if(!api.connected())return connectDialog();r.status='queued';r.error='';r.misses=0;r.pollStart=Date.now();saveRecords();renderGallery();poll();}
        else{e.currentTarget.disabled=true;try{await api.request('/cancel',{requestId:r.requestId});r.status='canceled';saveRecords();renderGallery();}catch(e){notify(e.message);renderGallery();}}
      });
      card.querySelector('img')?.addEventListener('error',e=>{e.target.replaceWith(Object.assign(document.createElement('span'),{className:'pg-help',textContent:'预览暂不可用，点击查看详情或下载'}));});
    });
    $('.pg-history-note').textContent=storageWarning||'历史记录仅保存在当前浏览器；收藏不会自动清理。';
  }
  function toggle(id){selecting=true;selected.has(id)?selected.delete(id):selected.add(id);renderGallery();}
  function reuse(r){modelId=r.plane.model;surface=r.kind;prompt=r.plane.prompt.text;settingsByModel[modelId]=structuredClone(r.plane.settings);media=structuredClone(r.plane.media);saveDraft();closeDialog();renderComposer();$('textarea').focus();$('textarea').scrollIntoView({block:'center'});}
  async function download(output){
    const r=await fetch(output.url,{credentials:'omit',signal:AbortSignal.timeout(60000)});if(!r.ok)throw Error('原站未允许下载，请使用原文件链接');
    const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='vision-'+Date.now()+'.'+(blob.type.split('/')[1]?.split(';')[0]||(output.kind==='video'?'mp4':'png'));a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
  }
  async function bulk(action){
    if(action==='all'){selected=new Set(galleryRows().map(r=>r.id));renderGallery();return;}
    const list=records.filter(r=>selected.has(r.id));
    if(action==='favorite'){for(const r of list)r.favorite=true;saveRecords();renderGallery();notify('已收藏所选作品');}
    if(action==='download'){let count=0,failed=0;for(const r of list)for(const output of r.outputs||[]){try{await download(output);count++;}catch{failed++;}}notify(`已下载 ${count} 个文件${failed?'，'+failed+' 个文件被原站限制下载':''}`);}
    if(action==='delete'){
      if(list.some(active)){notify('请先取消正在生成的任务，再删除记录');return;}
      clearTimeout(undoTimer);undoRows=list;records=records.filter(r=>!selected.has(r.id));selected.clear();await saveRecords();renderGallery();
      $('.pg-undo').hidden=false;$('.pg-undo span').textContent=`已删除 ${list.length} 条记录`;undoTimer=setTimeout(()=>{undoRows=[];$('.pg-undo').hidden=true;},6000);
    }
  }
  function viewer(id,index=0){
    const r=records.find(r=>r.id===id),output=r?.outputs?.[index];if(!output)return;
    const list=galleryRows().flatMap(row=>(row.outputs||[]).map((o,i)=>({id:row.id,index:i}))),position=list.findIndex(i=>i.id===id&&i.index===index);
    const d=openDialog(r.model,`<div class="pg-viewer-layout"><div class="pg-viewer-media">${output.kind==='video'?`<video src="${esc(output.url)}" controls playsinline></video>`:`<img src="${esc(output.url)}" alt="生成结果">`}</div><div class="pg-viewer-info"><h3>提示词</h3><p>${esc(r.plane.prompt.text)}</p><button type="button" class="pill-btn shadow pg-copy">${icon('copy')}复制</button><dl class="pg-viewer-settings">${Object.entries(r.plane.settings).map(([key,val])=>`<div><dt>${esc(settingNames[key]||key)}</dt><dd>${esc(typeof val==='boolean'?(val?'开启':'关闭'):val)}</dd></div>`).join('')}</dl><p>${shortDate(r.created)}</p><div class="pg-dialog-actions"><button type="button" class="pill-btn shadow pg-view-favorite">${r.favorite?'取消收藏':'收藏'}</button><button type="button" class="pill-btn dark pg-reuse">再次创作</button></div></div></div><div class="pg-viewer-controls"><span class="pg-count">${position+1} / ${list.length}</span><a class="pill-btn shadow" href="${esc(output.url)}" target="_blank" rel="noopener noreferrer">原文件 ${icon('external')}</a><button type="button" class="pill-btn shadow pg-download">${icon('download')}下载</button><button type="button" class="ibtn pg-previous" aria-label="上一张" ${position===0?'disabled':''}>${icon('previous')}</button><button type="button" class="ibtn pg-next" aria-label="下一张" ${position===list.length-1?'disabled':''}>${icon('next')}</button></div>`,true);
    d.querySelector('.pg-copy').onclick=()=>navigator.clipboard.writeText(r.plane.prompt.text).then(()=>notify('提示词已复制')).catch(()=>notify('复制失败，请手动选择提示词'));
    d.querySelector('.pg-reuse').onclick=()=>reuse(r);d.querySelector('.pg-view-favorite').onclick=()=>{r.favorite=!r.favorite;saveRecords();renderGallery();d.querySelector('.pg-view-favorite').textContent=r.favorite?'取消收藏':'收藏';};
    d.querySelector('.pg-download').onclick=async e=>{e.target.disabled=true;try{await download(output);}catch(e){notify(e.message);}finally{e.target.disabled=false;}};
    function turn(delta){const target=list[position+delta];if(target)viewer(target.id,target.index);}
    d.querySelector('.pg-previous').onclick=()=>turn(-1);d.querySelector('.pg-next').onclick=()=>turn(1);d.onkeydown=e=>{if(e.key==='ArrowLeft'){e.preventDefault();turn(-1);}if(e.key==='ArrowRight'){e.preventDefault();turn(1);}};
  }
  function assetDialog(role){
    if((media[role]||[]).length>=model().roles[role]){notify('已达到这个模型的素材数量上限');return;}
    const kind=kindFor(role),accept=kind==='image'?'image/png,image/jpeg,image/webp,image/gif':kind==='video'?'video/mp4,video/quicktime':'audio/wav,audio/mpeg';
    const d=openDialog('添加'+roleNames[role],`<p>选择已上传素材或生成结果，也可以添加公开的 HTTPS 素材地址。</p><button type="button" class="pg-upload-button">${icon('upload')}上传${kind==='image'?'图片':kind==='video'?'视频':'音频'}</button><input type="file" accept="${accept}" hidden><div class="pg-mode"><button type="button" class="chip on" data-library="uploads">已上传</button><button type="button" class="chip" data-library="history">生成结果</button></div><div class="pg-library"></div><form class="pg-url-form"><input type="url" required placeholder="https://…" aria-label="素材地址"><button type="submit" class="pill-btn shadow">添加链接</button></form><p class="pg-error" role="alert"></p><small class="pg-help">${kind==='image'?'图片最多 20 MB':'视频或音频最多 100 MB'}，上传到 Higgsfield 后才会加入素材。</small>`);
    let tab='uploads';
    const items=()=>tab==='uploads'?uploads.filter(i=>i.kind===kind):records.flatMap(r=>(r.outputs||[]).filter(o=>o.kind===kind).map(o=>({...o,name:r.model})));
    const paint=()=>{d.querySelector('.pg-library').innerHTML=items().map((item,i)=>`<button type="button" data-item="${i}" title="${esc(item.name||roleNames[role])}">${kind==='audio'?`<span>${esc(item.name||'音频')}</span>`:mediaHTML(item)}</button>`).join('')||'<p>暂无可用素材。</p>';d.querySelectorAll('[data-item]').forEach(b=>b.onclick=()=>attach(items()[Number(b.dataset.item)]));};
    const attach=item=>{if(model().roles[role]&&(media[role]||[]).length<model().roles[role]){(media[role]||=[]).push({url:item.url,name:item.name,role});saveDraft();renderComposer();closeDialog();}};
    d.querySelectorAll('[data-library]').forEach(b=>b.onclick=()=>{tab=b.dataset.library;d.querySelectorAll('[data-library]').forEach(x=>x.classList.toggle('on',x===b));paint();});
    d.querySelector('form').onsubmit=e=>{e.preventDefault();const url=publicURL(d.querySelector('[type=url]').value);if(!url){d.querySelector('.pg-error').textContent='请填写可公开访问的 HTTPS 素材地址';return;}attach({url,name:roleNames[role]});};
    d.querySelector('.pg-upload-button').onclick=()=>{if(!api.connected()){connectDialog();return;}d.querySelector('[type=file]').click();};
    d.querySelector('[type=file]').onchange=async e=>{
      const file=e.target.files[0];if(!file)return;const button=d.querySelector('.pg-upload-button');
      if(file.size>(kind==='image'?20:100)*1024*1024){d.querySelector('.pg-error').textContent='文件超过大小限制';return;}
      uploading=true;button.disabled=true;button.textContent='正在上传…';updateConnection();
      try{
        const signed=await api.request('/upload',{contentType:file.type});
        if(!publicURL(signed.upload_url)||!publicURL(signed.public_url))throw Error('上传服务返回了无效地址');
        const headers=new Headers(signed.upload_headers||{});headers.delete('Authorization');headers.delete('Cookie');
        const r=await fetch(signed.upload_url,{method:'PUT',headers,body:file,credentials:'omit',signal:AbortSignal.timeout(120000)});if(!r.ok)throw Error('素材上传失败，请重试');
        const item={url:signed.public_url,kind,name:file.name};uploads.unshift(item);uploads=uploads.slice(0,100);await save('uploads',uploads);if(d.isConnected)attach(item);
      }catch(e){if(d.isConnected)d.querySelector('.pg-error').textContent=e.message;}finally{uploading=false;button.disabled=false;button.innerHTML=icon('upload')+'上传素材';updateConnection();}
    };paint();
  }
  view.innerHTML=`<header class="head"><h1>Playground</h1><span class="sub">图像与视频创作</span><div class="pg-head-actions"><a class="pill-btn grey" href="${catalog.source}" target="_blank" rel="noopener noreferrer">OpenHiggsfield ${icon('external')}</a><button type="button" class="pill-btn shadow pg-key"></button></div></header><div class="pg-layout"><form class="pg-composer"></form><section class="pg-history" aria-label="创作记录"><div class="pg-gallery-bar"><div class="pg-tabs" aria-label="作品筛选"></div><button type="button" class="pill-btn shadow pg-select-toggle">选择</button></div><div class="pg-selection" hidden></div><div class="pg-undo" hidden><span></span><button type="button" class="pill-btn shadow">撤销</button></div><div class="pg-grid"></div><div class="pg-empty"></div><p class="pg-help pg-history-note"></p></section></div>`;
  $('.pg-key').onclick=connectDialog;$('.pg-composer').onsubmit=e=>{e.preventDefault();generate();};$('.pg-select-toggle').onclick=()=>{selecting=!selecting;selected.clear();renderGallery();};
  $('.pg-undo button').onclick=async()=>{clearTimeout(undoTimer);records=[...records,...undoRows].sort((a,b)=>b.created-a.created);undoRows=[];$('.pg-undo').hidden=true;await saveRecords();renderGallery();};
  view.addEventListener('keydown',e=>{if(e.key==='Escape'&&!dialog){selecting=false;selected.clear();renderGallery();}});
  renderComposer();renderGallery();
  return {element:view,activate(){visible=true;updateConnection();if(api.connected())api.request('/connection').catch(()=>updateConnection());schedule();},deactivate(){visible=false;clearTimeout(timer);closeDialog();view.querySelectorAll('video').forEach(v=>v.pause());}};
}

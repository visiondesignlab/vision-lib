/* Vision CMS — authenticated content view within the shared Vision Lib shell. */
import './cms-select.js';
import {directoryManager} from './cms-directory.js';
export function createCMS({navigate, replaceURL, onContentChange, onCounts, onSessionChange = () => {}}) {
const root = document.createElement('div');
root.id = 'cms';root.className = 'cms-body';
const $ = (s, el = root) => el.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const TYPES = {video:'视频案例',showcase:'灵感库',graphic:'平面',brand_skill:'品牌 Skill',skill_repo:'Skill 仓库'};
const STATUS = {all:'全部内容',draft:'草稿',pending:'待审核',published:'已发布',rejected:'已退回',archived:'已下架'};
const ACTION = {migrate:'迁移栏目',create:'创建内容',edit:'保存草稿',submit:'提交审核',approve:'审核通过并发布',reject:'退回修改',unpublish:'下架内容'};
let csrf = '', cases = [], dirty = false, busy = false, routeId = 0, active = false;
let filter = {q:'',type:'all'};

let tableObserver = null, tableLoadFrame = 0, stopDirectory = null;
function stopTableLoading(){
  stopDirectory?.();stopDirectory=null;
  tableObserver?.disconnect();tableObserver=null;
  cancelAnimationFrame(tableLoadFrame);tableLoadFrame=0;
}
localStorage.removeItem('caselib_token');
const badge = c => `<span class="badge ${esc(c.status)}">${STATUS[c.status] || esc(c.status)}</span>`;
const date = s => (s || '').slice(0,16).replace('T',' ');
function toast(message){ const el=document.querySelector('#toast');el.textContent=message;el.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.hidden=true,4000); }
async function api(path, options={}){
  const headers = {'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':csrf}:{}),...options.headers};
  const response = await fetch(path,{credentials:'same-origin',...options,headers});
  const value = await response.json().catch(()=>({}));
  if(response.status===401)onSessionChange(false);
  if(!response.ok) throw Object.assign(new Error(value.error || '请求失败，请重试'),{status:response.status});
  return value;
}
const post = (path,data={}) => api(path,{method:'POST',body:JSON.stringify(data)});
function leave(){return !busy && (!dirty || confirm('有尚未保存的修改，确定离开吗？'));}
const go = url => navigate(url);
window.addEventListener('beforeunload',e=>{if(active&&(dirty||busy)){e.preventDefault();e.returnValue='';}});
function deactivate(){
  if(!active)return;
  active=false;++routeId;dirty=false;csrf='';cases=[];
  stopTableLoading();window.CMSSelect.close();
  root.querySelectorAll('dialog').forEach(d=>d.close());
  root.replaceChildren();
}
function login(){
  stopTableLoading();csrf='';onSessionChange(false);root.innerHTML=`<section class="login-main"><div class="head"><h1>内容管理</h1><span class="sub">登录后管理内容、审核与发布</span></div><form class="login-form"><h2>进入内容管理平台</h2><p>输入管理密码，继续你的内容工作。</p><label class="field" for="password"><span>管理密码</span></label><div class="password-wrap"><input id="password" type="password" required autocomplete="current-password" placeholder="请输入密码" maxlength="256"><button id="show-password" type="button" aria-label="显示密码">显示</button></div><div class="error" role="alert" id="login-error"></div><button type="submit" class="btn primary">登录工作台</button><a class="login-back" href="/" data-link>返回内容浏览</a><p class="login-note">内容审核发布后，才会出现在用户浏览页面。</p></form></section>`;
  const form=$('.login-form');$('#show-password').onclick=()=>{const p=$('#password');p.type=p.type==='password'?'text':'password';$('#show-password').textContent=p.type==='password'?'显示':'隐藏';$('#show-password').setAttribute('aria-label',p.type==='password'?'显示密码':'隐藏密码');};
  form.onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;const button=$('[type=submit]',form);button.disabled=true;button.textContent='正在登录…';$('#login-error').textContent='';try{const r=await post('/api/auth/login',{password:$('#password').value});csrf=r.csrf;onSessionChange(true);replaceURL('/cms');await render();}catch(err){$('#login-error').textContent=err.message;$('#password').focus();}finally{busy=false;button.disabled=false;button.textContent='登录工作台';}};
  $('#password').focus();
}
function shell(active, crumb){
  const pending=cases.filter(c=>c.status==='pending').length;
  root.innerHTML=`<div class="workspace"><header class="cms-subnav"><span class="muted">内容管理</span><nav aria-label="CMS 二级导航">${[['overview','/cms','工作台'],['content','/cms/content','全部内容'],['mine','/cms/content?owner=mine','我的内容'],['review','/cms/content?status=pending','审核队列'],['ai-nav','/cms/ai-nav','AI 导航'],['settings','/cms/settings','账号设置']].map(([key,url,title])=>`<a class="chip ${active===key?'on':''}" ${active===key?'aria-current="page"':''} data-nav href="${url}">${title}${key==='review'&&pending?`<span class="n">${pending}</span>`:''}</a>`).join('')}</nav><button class="btn small" id="cms-logout">退出登录</button></header><div class="main" id="main"></div></div>`;
  $('#cms-logout').onclick=async()=>{if(!leave())return;busy=true;try{await post('/api/auth/logout');dirty=false;login();}catch(err){toast(err.message);}finally{busy=false;}};
}

function updateCounts(records) {
  onCounts({total:records.length, published:records.filter(c=>c.live_status==='published').length,
    pending:records.filter(c=>c.status==='pending').length});
}
async function refreshCounts(){
  if(!active || !csrf)return;
  const seq=routeId;
  try { const data=await api('/api/admin/cases?status=all'); if(active && seq===routeId && csrf)updateCounts(data.cases); } catch {}
}
async function render(){
  if(!active)return;
  stopTableLoading();window.CMSSelect.close();const seq=++routeId;
  try{
    const session=await api('/api/auth/session');if(seq!==routeId)return;csrf=session.csrf;onSessionChange(true);
    if(location.pathname==='/cms/ai-nav'){
      const db=await api('/api/admin/ai-directory');if(seq!==routeId)return;
      refreshCounts();shell('ai-nav','AI 导航');stopDirectory=directoryManager($('#main'),db,{esc,dialog,post,toast,reload:render,
        markDirty:value=>{dirty=value;},markBusy:value=>{if(value&&busy)return false;busy=value;return true;}});return;
    }
    const data=await api('/api/admin/cases?status=all');if(seq!==routeId)return;cases=data.cases;updateCounts(cases);
    const url=new URL(location.href), path=url.pathname;
    if(path==='/cms/new'){shell('content','新建内容');return editor();}
    const edit=path.match(/^\/cms\/edit\/([\w.-]+)$/);
    if(edit){const c=cases.find(c=>c.id===edit[1]);shell('content','编辑内容');if(!c)return $('#main').innerHTML=empty('内容不存在','这个内容可能已被移动。');return editor(c);}
    if(path==='/cms/settings'){shell('settings','账号设置');return settings();}
    if(path==='/cms/content'){shell(url.searchParams.get('owner')==='mine'?'mine':url.searchParams.get('status')==='pending'?'review':'content','内容库');return contentPage();}
    shell('overview','工作台');overview();
  }catch(err){
    if(seq!==routeId)return;
    if(err.status===401)return login();
    root.innerHTML=`<div class="empty"><h3>工作台暂时无法加载</h3><p>${esc(err.message)}</p><button class="btn" id="retry">重新加载</button></div>`;$('#retry').onclick=render;
  }
}
function empty(title,description,create=false){return `<div class="empty"><div class="empty-icon" aria-hidden="true">▤</div><h3>${esc(title)}</h3><p>${esc(description)}</p>${create?'<a data-nav href="/cms/new" class="btn primary">＋ 新建内容</a>':''}</div>`;}
function overview(){
  const count=st=>cases.filter(c=>c.status===st).length;
  $('#main').innerHTML=`<div class="page-head"><div><div class="eyebrow">YOUR CONTENT, AT A GLANCE</div><h1>内容工作台</h1><p>管理草稿、审核和已发布内容。</p></div><a class="btn primary" href="/cms/new" data-nav>＋ 新建内容</a></div><div class="stats">${[['draft','草稿箱','继续完善你的创作'],['pending','等待审核','确认后发布到前台'],['published','已发布','用户正在浏览的内容'],['rejected','退回修改','完善后可再次提交']].map(([st,label,hint])=>`<a data-nav href="/cms/content?status=${st}" class="stat ${st}"><span class="label">${label}<span aria-hidden="true">↗</span></span><strong>${st==='published'?cases.filter(c=>c.live_status==='published').length:count(st)}</strong><span class="hint">${hint}</span></a>`).join('')}</div><section class="panel"><div class="panel-heading"><div><h2>最近更新</h2><p>最近保存与审核的内容</p></div><a class="btn small" data-nav href="/cms/content">全部内容 →</a></div><div id="table"></div></section>`;
  renderTable(cases.slice(0,8),false);
}
function contentPage(){
  const url=new URL(location.href), mine=url.searchParams.get('owner')==='mine', status=url.searchParams.get('status')||'all';
  const requestedType=url.searchParams.get('type');
  if(requestedType)filter.type=TYPES[requestedType]?requestedType:'all';
  const pool=mine?cases.filter(c=>c.origin==='cms'):cases;
  $('#main').innerHTML=`<div class="page-head"><div><div class="eyebrow">CONTENT LIBRARY</div><h1>${mine?'我的内容':status==='pending'?'审核队列':'全部内容'}</h1><p>${mine?'在 CMS 中创建的内容，草稿、审核和发布都在这里。':'统一管理作品、灵感与 Skill，查看每一条内容的发布进度。'}</p></div><a class="btn primary" data-nav href="/cms/new">＋ 新建内容</a></div><section class="panel"><div class="filters"><div class="tabs" role="group" aria-label="内容状态">${Object.entries(STATUS).map(([key,label])=>`<button class="tab ${status===key?'on':''}" aria-pressed="${status===key}" data-status="${key}">${key==='all'?'全部':label}<span>${key==='all'?pool.length:pool.filter(c=>key==='published'?c.live_status==='published':c.status===key).length}</span></button>`).join('')}</div></div><div class="filters"><span class="muted">内容类型</span><select id="type-filter" aria-label="筛选内容类型"><option value="all">全部类型</option>${Object.entries(TYPES).map(([key,title])=>`<option value="${key}" ${filter.type===key?'selected':''}>${title}</option>`).join('')}</select><div class="search"><input type="search" id="search" aria-label="搜索内容" placeholder="搜索标题、作者、标签…" value="${esc(filter.q)}"></div></div><div id="table"></div></section>`;
  root.querySelectorAll('[data-status]').forEach(b=>b.onclick=()=>{url.searchParams.set('status',b.dataset.status);replaceURL(url);contentPage();});
  $('#type-filter').onchange=e=>{filter.type=e.target.value;url.searchParams.set('type',filter.type);replaceURL(url);list();};
  window.CMSSelect.enhance($('#type-filter'),'筛选内容类型');
  $('#search').oninput=e=>{filter.q=e.target.value;list();};
  function list(){const q=filter.q.trim().toLowerCase();const rows=pool.filter(c=>(status==='all'||(status==='published'?c.live_status==='published':c.status===status))&&(filter.type==='all'||c.type===filter.type)&&(!q||[c.title,c.category,c.source?.author,...(c.tags||[])].join(' ').toLowerCase().includes(q)));renderTable(rows,true);}
  list();
}
const operations = {
  submit: ['提交审核', c => ['draft','rejected','archived'].includes(c.status)],
  approve: ['发布', c => c.status === 'pending'],
  reject: ['退回', c => c.status === 'pending'],
  unpublish: ['下架', c => c.live_status === 'published'],
  delete: ['删除', c => !!c.id]
};
const transferTargets = {video:'showcase',showcase:'video'};
function tableRow(c, selectable){
  const target=transferTargets[c.type];
  const matches=c.duplicates?.length ? `<details class="duplicate-info"><summary>疑似重复（${c.duplicates.length}）</summary><ul>${duplicateList(c.duplicates)}</ul></details>` : '';
  const move=target ? `<button class="btn small" data-action="migrate">迁移到${TYPES[target]}</button>` : '';
  return `<tr data-id="${esc(c.id)}"><td><div class="title-cell">${selectable?`<label class="row-select"><input type="checkbox" data-select-id="${esc(c.id)}" aria-label="选择：${esc(c.title)}"></label>`: ''}<span class="thumb"><img src="${esc(c.media?.thumbnail||'/static/cms-placeholder.svg')}" alt="" loading="lazy"></span><div class="title-text"><button data-action="edit">${esc(c.title||'未命名内容')}</button><small>${esc(c.source?.author||'团队创作')} ${c.origin==='cms'?'· 我的内容':''}</small>${matches}</div></div></td><td data-label="类型 / 分类">${TYPES[c.type]||esc(c.type)}<div class="hint" style="font-size:10px;margin-top:5px">${esc(c.category||'未分类')}</div></td><td data-label="状态">${badge(c)}${c.has_revision?'<div class="hint" style="font-size:10px;margin-top:5px">线上版本保持已发布</div>':''}</td><td class="muted" data-label="最近更新" style="font-size:11px">${esc(date(c.updated_at||c.added_at))}</td><td><div class="row-actions"><button class="btn small" data-action="preview">预览</button><button class="btn small" data-action="edit">编辑</button>${move}${Object.entries(operations).filter(([, [, allowed]])=>allowed(c)).map(([kind,[label]])=>`<button class="btn small ${kind==='approve'?'primary':['reject','delete'].includes(kind)?'danger':''}" data-action="${kind}">${kind==='delete' && c.live_status==='published'?'下架并删除':label}</button>`).join('')}</div></td></tr>`;
}
function renderTable(list,scrollLoad){
  stopTableLoading();
  const table=$('#table'), total=list.length, batchSize=15;
  table.onchange=null;
  if(!total){
    table.innerHTML=empty('这里还没有内容',filter.q?'试试其他关键词或筛选条件。':'创建你的第一条内容，或切换状态查看已有内容。',true);
    table.onclick=null;
    return;
  }
  const selected=new Set();
  const toolbar=scrollLoad ? `<div class="filters bulk-bar"><label><input type="checkbox" data-all> 全选筛选结果（${total}）</label><span data-count aria-live="polite"></span><button type="button" class="btn small" data-clear hidden>清空选择</button><div data-operations></div></div>` : '';
  table.innerHTML=`${toolbar}<div class="table-wrap"><table><thead><tr><th>内容</th><th>类型 / 分类</th><th>状态</th><th>最近更新</th><th>操作</th></tr></thead><tbody></tbody></table></div>${scrollLoad?'<div class="load-status" role="status" aria-live="polite" aria-atomic="true"></div>':''}`;
  const body=$('tbody',table), sentinel=$('.load-status',table);
  let shown=0;
  function appendBatch(){
    const next=Math.min(shown+(scrollLoad?batchSize:total),total);
    // Append only new rows to preserve scroll position, focus and existing media.
    body.insertAdjacentHTML('beforeend',list.slice(shown,next).map(c=>tableRow(c,scrollLoad)).join(''));
    shown=next;
    if(scrollLoad) syncSelection();
    if(sentinel)sentinel.textContent=shown===total?`共 ${total} 条内容 · 已全部加载`:`已加载 ${shown} / ${total} 条内容 · 向下滚动继续加载`;
  }
  function syncSelection(){
    const all=$('[data-all]',table), picked=list.filter(c=>selected.has(c.id));
    all.checked=selected.size===total; all.indeterminate=selected.size>0&&!all.checked;
    $('[data-count]',table).textContent=selected.size?`已选 ${selected.size} 条`:'';
    $('[data-clear]',table).hidden=!selected.size;
    for(const cb of body.querySelectorAll('[data-select-id]')){
      cb.checked=selected.has(cb.dataset.selectId);cb.closest('tr').classList.toggle('picked',cb.checked);
    }
    $('[data-operations]',table).innerHTML=selected.size?Object.entries(operations).map(([kind,[label,allowed]])=>{
      const n=picked.filter(allowed).length;
      return `<button class="btn small ${kind==='delete'?'danger':''}" data-batch="${kind}" ${n?'':'disabled'}>${label}（${n}）</button>`;
    }).join('') + Object.entries(transferTargets).map(([from,to])=>{
      const count=picked.filter(c=>c.type===from).length;
      return count ? `<button class="btn small" data-move="${to}">迁移到${TYPES[to]}（${count}）</button>` : '';
    }).join(''):'';
  }
  if(scrollLoad)table.onchange=e=>{
    if(e.target.matches('[data-all]')){selected.clear();if(e.target.checked)for(const c of list)selected.add(c.id);}
    else if(e.target.matches('[data-select-id]')){const id=e.target.dataset.selectId;if(e.target.checked)selected.add(id);else selected.delete(id);}
    else return;
    syncSelection();
  };
  table.onclick=e=>{
    if(e.target.closest('[data-clear]')){selected.clear();syncSelection();return;}
    const move=e.target.closest('[data-move]');
    if(move){
      const rows=list.filter(c=>selected.has(c.id)&&transferTargets[c.type]===move.dataset.move);
      return migrate(rows,move.dataset.move,selected.size-rows.length);
    }
    const batch=e.target.closest('[data-batch]');
    if(batch){batchAction(list.filter(c=>selected.has(c.id)), batch.dataset.batch);return;}
    const button=e.target.closest('[data-action]');
    if(!button||!table.contains(button))return;
    const c=list.find(c=>c.id===button.closest('tr').dataset.id);
    if(!c)return;
    if(button.dataset.action==='edit')go('/cms/edit/'+c.id);
    else if(button.dataset.action==='preview')preview(c);
    else if(button.dataset.action==='migrate')migrate([c],transferTargets[c.type]);
    else action(c,button.dataset.action);
  };
  appendBatch();
  if(!scrollLoad||shown===total)return;
  if(!('IntersectionObserver' in window)){
    while(shown<total)appendBatch();
    return;
  }
  const observer=new IntersectionObserver(entries=>{
    if(tableObserver!==observer||!table.isConnected||!entries.some(entry=>entry.isIntersecting))return;
    observer.unobserve(sentinel);
    appendBatch();
    if(shown===total){observer.disconnect();tableObserver=null;return;}
    // Reobserve after layout so tall viewports keep filling until the end is below the fold.
    tableLoadFrame=requestAnimationFrame(()=>{
      tableLoadFrame=0;
      if(tableObserver===observer&&table.isConnected)observer.observe(sentinel);
    });
  },{rootMargin:'0px 0px 240px 0px'});
  tableObserver=observer;
  observer.observe(sentinel);
}

function dialog(html){const d=document.createElement('dialog');d.className='dialog';d.innerHTML=html;root.append(d);d.addEventListener('close',()=>d.remove());d.addEventListener('cancel',e=>{if(d.dataset.working)e.preventDefault();});d.addEventListener('click',e=>{if(e.target===d&&!d.dataset.working){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}});d.showModal();d.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>d.close());return d;}
function mediaHTML(c){const m=c.media||{};return m.video?window.VisionSite.videoPlayer(m.video,m.thumbnail):`<img src="${esc(m.thumbnail||m.images?.[0]||'/static/cms-placeholder.svg')}" alt="${esc(c.title||'内容封面')}">`;}
function preview(c){dialog(`<div style="display:flex;justify-content:space-between;align-items:center"><span class="eyebrow">CONTENT PREVIEW · 仅管理员可见</span><button type="button" class="btn ghost preview-close" data-close aria-label="关闭预览"><svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><path d="m4 4 8 8m0-8-8 8"/></svg></button></div><div class="preview-media">${mediaHTML(c)}</div>${badge(c)}<h2 style="margin-top:14px">${esc(c.title||'未命名内容')}</h2><p>${esc(c.subtitle||'')}</p>${c.description?`<p style="white-space:pre-wrap">${esc(c.description)}</p>`:''}${c.prompt?`<h3 style="font-size:13px;margin-top:22px">示例 Prompt</h3><pre>${esc(c.prompt)}</pre>`:''}${c.how_to?.length?`<ol>${c.how_to.map(x=>`<li style="padding:6px 0;line-height:1.7">${esc(x)}</li>`).join('')}</ol>`:''}${c.assets?.length?`<div class="asset-list">${c.assets.map(x=>`<div class="asset-row"><a href="${esc(x.url)}" target="_blank" rel="noopener">↗ ${esc(x.name)}</a></div>`).join('')}</div>`:''}${c.source?.url?`<p>来源：<a href="${esc(c.source.url)}" target="_blank" rel="noopener">${esc(c.source.author||c.source.url)} ↗</a></p>`:''}<div class="dialog-actions"><button class="btn" data-close>关闭预览</button></div>`);}
function duplicateList(peers) {
  return peers.map(p => `<li><a href="/cms/edit/${encodeURIComponent(p.id)}">${esc(p.title)} ↗</a> · ${esc(TYPES[p.type])} · ${esc(p.reasons.join('、'))}</li>`).join('');
}
async function migrate(rows, target, skipped=0) {
  if (busy || !rows.length) return;
  const request = {target, items:rows.map(c => ({id:c.id, _version:c._version || 0}))};
  const sourceURL = '/api/admin/video-migration';
  busy=true;
  let conflicts;
  try { ({conflicts} = await post(sourceURL, request)); }
  catch (err) { toast(err.message); return; }
  finally { busy=false; }
  if (!active) return;
  const categories = [...new Set(cases.filter(c=>c.type===target).map(c=>c.category).filter(Boolean))].sort();
  const initial = rows.every(c=>c.category===rows[0].category) && categories.includes(rows[0].category) ? rows[0].category : '';
  const duplicates = Object.keys(conflicts).length;
  const d=dialog(`<form><h2>迁移到${TYPES[target]}</h2><p>${rows.length} 条内容将移动到目标栏目，沿用原链接和发布状态。${skipped?`另有 ${skipped} 条不适用，已跳过。`:''}</p><ul class="batch-items">${rows.map(c=>`<li>${esc(c.title)}${conflicts[c.id]?`<strong class="duplicate-label">疑似重复</strong><ul>${duplicateList(conflicts[c.id])}</ul>`:''}</li>`).join('')}</ul><label class="field"><span>目标分类</span><input name="category" list="migration-categories" value="${esc(initial)}" required maxlength="500" placeholder="选择或输入分类"></label><datalist id="migration-categories">${categories.map(name=>`<option value="${esc(name)}"></option>`).join('')}</datalist>${duplicates?`<label class="check-field"><input type="checkbox" required> 已核对 ${duplicates} 条疑似重复内容，保留各条记录并迁移</label>`:''}<div class="error" role="alert"></div><div class="dialog-actions"><button type="button" class="btn" data-close>取消</button><button class="btn primary" type="submit">确认迁移</button></div></form>`);
  $('form',d).onsubmit=async event=>{
    event.preventDefault();
    if(busy)return;
    busy=true;d.dataset.working='true';
    for(const b of d.querySelectorAll('button')) b.disabled=true;
    try {
      const result=await post(sourceURL,{...request,apply:true,confirmed:conflicts,category:$('[name=category]',d).value});
      d.close();onContentChange();await render();toast(`已迁移 ${result.moved} 条到${TYPES[target]}`);
    } catch(err) { $('.error',d).textContent=err.message; }
    finally { busy=false;delete d.dataset.working;for(const b of d.querySelectorAll('button')) b.disabled=false; }
  };
}
function action(c,kind){
  const live=c.live_status==='published';
  const labels={delete:[live?'下架并删除内容':'删除内容',live?'公开版本和未发布的修订都将从内容库移除，无法恢复。':'删除后将从内容库移除，无法在平台内恢复。',live?'确认下架并删除':'确认删除'],submit:['提交审核','提交后，内容将进入审核队列。审核通过后才会公开展示。','提交审核'],approve:['确认发布内容','发布后，所有普通用户都可以在对应栏目浏览这条内容。','确认发布'],reject:['退回修改','填写具体原因，方便继续修改。重新提交后可以再次审核。','确认退回'],unpublish:['下架内容','下架后，普通用户将无法浏览这条内容。内容仍保留在 CMS，可以修改后重新提交。','确认下架']};
  const [title,description,button]=labels[kind];
  const d=dialog(`<form><h2>${title}</h2><p><b>${esc(c.title||'未命名内容')}</b></p><p>${description}</p>${kind==='reject'?'<label class="field"><span>退回原因</span><textarea name="note" required maxlength="2000" placeholder="请说明需要调整的地方"></textarea></label>':''}<div class="error" role="alert"></div><div class="dialog-actions"><button type="button" class="btn" data-close>取消</button><button type="submit" class="btn ${kind==='delete'?'danger':'primary'}">${button}</button></div></form>`);
  $('form',d).onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;const b=$('[type=submit]',d);b.disabled=true;try{await post(`/api/admin/cases/${c.id}/${kind}`,{_version:c._version||0,note:$('[name=note]',d)?.value||'',...deleteConfirmation(kind,c)});d.close();if(kind==='unpublish')dirty=false;if(['approve','unpublish','delete'].includes(kind))onContentChange();toast({delete:'内容已删除',submit:'已提交审核',approve:'已发布，普通用户现在可以浏览',reject:'已退回，可修改后重新提交',unpublish:'已下架，前台已隐藏'}[kind]);if(kind==='delete'&&location.pathname.startsWith('/cms/edit/')){dirty=false;busy=false;go('/cms/content');}else await render();}catch(err){$('.error',d).textContent=err.message;b.disabled=false;}finally{busy=false;}};
}
function deleteConfirmation(kind,c){return kind==='delete'?{confirm_delete:true,remove_live:c.live_status==='published'}:{};}
function batchAction(picked,kind){
  if(busy)return;
  const [label,allowed]=operations[kind], rows=picked.filter(allowed), skipped=picked.length-rows.length;
  if(!rows.length)return;
  const liveCount=rows.filter(c=>c.live_status==='published').length;
  const deletion=kind==='delete'?(liveCount?`其中 ${liveCount} 条仍在公开展示，将一并下架。 `:'')+'删除后无法在平台内恢复。':'';
  const d=dialog(`<form><h2>批量${label}</h2><p>将${label}以下 ${rows.length} 条内容。${skipped?`另有 ${skipped} 条状态不适用，将跳过。`:''}${deletion}</p><ul class="batch-items">${rows.map(c=>`<li>${esc(c.title)}</li>`).join('')}</ul>${kind==='reject'?'<label class="field"><span>共同退回原因</span><textarea name="note" required maxlength="2000"></textarea></label>':''}<div class="error" role="status"></div><div class="dialog-actions"><button type="button" class="btn" data-close>取消</button><button type="submit" class="btn ${kind==='delete'?'danger':'primary'}">确认${label}</button></div></form>`);
  $('form',d).onsubmit=async e=>{
    e.preventDefault();if(busy)return;
    const note=$('[name=note]',d)?.value.trim()||'';
    if(kind==='reject'&&!note){$('.error',d).textContent='请填写退回原因';return;}
    busy=true;d.dataset.working='true';d.querySelectorAll('button,textarea').forEach(x=>x.disabled=true);
    let ok=0,attempted=0;const errors=[];
    try {
      for(const c of rows){
        $('.error',d).textContent=`正在处理 ${++attempted} / ${rows.length}…`;
        try{await post(`/api/admin/cases/${encodeURIComponent(c.id)}/${kind}`,{_version:c._version||0,note,...deleteConfirmation(kind,c)});ok++;}
        catch(err){
          errors.push([c.title,!err.status || err.status>=500?'结果未确认，请刷新核对。':err.message]);
          if(!err.status||[401,403].includes(err.status)||err.status>=500)break;
        }
      }
      d.close();if(ok && ['approve','unpublish','delete'].includes(kind))onContentChange();
      await render();
      const summary=`${label}成功 ${ok} 条，未完成 ${errors.length} 条，跳过 ${skipped} 条，未执行 ${rows.length-attempted} 条。`;
      if(errors.length&&csrf&&active)dialog(`<h2>批量${label}结果</h2><p>${summary}</p><ul class="batch-items">${errors.map(([title,msg])=>`<li>${esc(title)}：${esc(msg)}</li>`).join('')}</ul><div class="dialog-actions"><button class="btn" data-close>关闭</button></div>`);
      else toast(summary);
    }finally{busy=false;}
  };
}
function field(name,label,value='',placeholder='',type='text'){return `<label class="field"><span>${label}</span><input name="${name}" type="${type}" value="${esc(value)}" placeholder="${esc(placeholder)}" ${type==='text'?'maxlength="500"':''}></label>`;}
function area(name,label,value='',placeholder='',rows=5){return `<label class="field"><span>${label}</span><textarea name="${name}" rows="${rows}" maxlength="50000" placeholder="${esc(placeholder)}">${esc(value)}</textarea></label>`;}
function editor(original){
  const requestedType=new URL(location.href).searchParams.get('type');
  let c=structuredClone(original||{type:TYPES[requestedType]?requestedType:'video',status:'draft',title:'',category:'',source:{platform:'原创',author:'vision design'},media:{},assets:[],tags:[],how_to:[],tools:[],trust:'社区'});
  let media=structuredClone(c.media||{}),assets=structuredClone(c.assets||[]),uploading=0;
  $('#main').innerHTML=`<form id="editor"><div class="page-head"><div><a data-nav href="/cms/content" class="hint">← 返回内容库</a><h1>${c.id?'编辑内容':'新建内容'}</h1><p>${c.live_status==='published'?'修改将保存为新草稿，审核通过后更新线上版本。':'先保存你的创作，再提交审核。'}</p></div><div class="head-actions"><span class="hint" id="save-state">${c.id?'已保存':'尚未保存'}</span><button type="button" class="btn" id="preview">预览</button><button type="submit" class="btn" id="save">保存草稿</button><button type="button" class="btn primary" id="submit">保存并提交审核</button></div></div><div class="editor-error" id="editor-error" role="alert"></div><div class="editor"><div class="editor-main"><section class="section"><h2>基本信息</h2><p>清晰的标题与分类，让用户更容易发现你的内容。</p><div class="row2"><label class="field"><span>内容类型 *</span><select name="type">${Object.entries(TYPES).filter(([k])=>!original || k!==transferTargets[original.type]).map(([k,v])=>`<option value="${k}" ${c.type===k?'selected':''}>${v}</option>`).join('')}</select></label>${field('category','分类 *',c.category,'例如：营销产品、动效特效、品牌规范')}</div>${original && transferTargets[c.type]?`<button type="button" class="btn small" id="editor-migrate">迁移到${TYPES[transferTargets[c.type]]}</button>`:''}${field('title','标题 *',c.title,'给内容一个简洁、准确的标题')}${field('subtitle','一句话介绍',c.subtitle,'这条内容有什么值得关注的地方？')}${area('description','内容介绍',c.description,'描述作品背景、思路或适用场景。',4)}<div class="row2">${field('brand','品牌',c.brand,'例如：viaim')}${field('tags','标签',c.tags?.join('，'),'用逗号分隔')}</div></section><section class="section"><h2>作品与素材</h2><p>上传图片、视频或 Skill 文档。素材随内容一同发布。</p><div class="upload-area"><div class="upload-buttons"><button type="button" class="btn small" data-upload="cover">＋ 上传封面</button><button type="button" class="btn small" data-upload="image">＋ 上传图片</button><button type="button" class="btn small" data-upload="video">＋ 上传视频</button><button type="button" class="btn small" data-upload="attachment">＋ 添加附件</button></div><p>图片 JPG / PNG / WebP · 视频 MP4 / MOV / WebM（200 MB 内）<br>附件 MD / TXT / PDF · 图片与附件单个 20 MB 内</p><div id="upload-status" class="uploads-status" role="status"></div></div>${field('thumbnail','封面链接',media.thumbnail,'上传后自动填写，也可填写 https:// 链接')}${field('video','视频链接',media.video,'上传后自动填写，也可填写可直接播放的视频链接')}<div class="asset-list" id="assets"></div></section><section class="section"><h2>创作方法</h2><p>让别人不仅看到作品，也能理解和复用你的方法。</p>${area('prompt','示例 Prompt',c.prompt,'填写可复制使用的完整提示词。',7)}${area('how_to','操作步骤',c.how_to?.join('\n'),'每行一步，按操作顺序填写。',4)}${field('tools','使用工具',c.tools?.join('，'),'例如：Figma，Codex，After Effects')}${area('analysis','作品拆解',c.analysis,'记录创作要点、画面设计与实现思路。',4)}</section><section class="section"><h2>来源信息</h2><p>原创作品可以直接填写作者；引用作品请保留来源。</p><div class="row2">${field('author','作者',c.source?.author,'作者或团队名称')}${field('platform','来源平台',c.source?.platform,'原创、X、GitHub…')}</div>${field('source_url','来源链接',c.source?.url,'https://')}${field('author_url','作者主页',c.source?.author_url,'https://')}<div class="row2">${field('source_date','作品日期',c.source?.date?.slice(0,10)||'','','date')}${field('version','版本',c.version,'例如：1.0.0')}</div><label class="check-field"><input name="featured" type="checkbox" ${c.featured?'checked':''}> 在前台标为推荐内容</label>${area('notes','内部备注 · 仅管理员可见',c.notes,'记录需要关注的问题，不会展示给普通用户。',3)}</section></div><aside class="editor-side"><section class="section"><h2>内容预览</h2><div class="preview-media" id="mini-media"></div><div class="preview-title" id="mini-title"></div><div class="preview-desc" id="mini-desc"></div><div class="status-line"><span class="muted">当前状态</span>${badge(c)}</div>${c.live_status==='published'?'<div class="notice">已有线上版本。新的修改审核通过后才会替换，用户仍可浏览原版本。</div>':'<div class="notice">草稿和待审核内容仅管理员可见。确认发布后，将出现在前台对应栏目。</div>'}${c.id?`<button type="button" class="btn danger full" id="editor-delete">${c.live_status==='published'?'下架并删除':'删除内容'}</button>`:''}${c.status==='pending'?'<button type="button" class="btn primary full" id="editor-approve">审核并发布</button><button type="button" class="btn full" id="editor-reject">退回修改</button>':''}${c.live_status==='published'?`<button type="button" class="btn full danger" id="editor-unpublish">下架内容</button><a class="btn full" href="/c/${esc(c.id)}" target="_blank" rel="noopener">查看线上版本 ↗</a>`:''}</section><section class="section"><h2>操作记录</h2>${c.review_log?.length?`<ul class="log">${[...c.review_log].reverse().slice(0,8).map(log=>`<li>${ACTION[log.action]||esc(log.action)}<time>${esc(date(log.at))}</time>${log.note?`<p>${esc(log.note)}</p>`:''}</li>`).join('')}</ul>`:'<p style="margin:16px 0 0">保存内容后，这里会记录每次提交与审核。</p>'}</section></aside></div></form>`;
  const move=$('#editor-migrate');
  if(move)move.onclick=()=>dirty?toast('请先保存编辑，再迁移栏目'):migrate([original],transferTargets[original.type]);
  const form=$('#editor'),val=name=>form.elements.namedItem(name)?.value||'';
  const unpublish=$('#editor-unpublish');if(unpublish)unpublish.onclick=()=>{if(leave())action(c,'unpublish');};
  function collect(){const copy={...media,thumbnail:val('thumbnail').trim(),video:val('video').trim()};if(copy.video!==media.video){copy.preview='';delete copy.specs;}copy.kind=copy.video?'video':copy.images?.length?'images':'image';return {type:val('type'),category:val('category'),title:val('title'),subtitle:val('subtitle'),description:val('description'),brand:val('brand'),tags:val('tags').split(/[,，]/).map(s=>s.trim()).filter(Boolean),prompt:val('prompt'),how_to:val('how_to').split('\n').map(s=>s.trim()).filter(Boolean),tools:val('tools').split(/[,，]/).map(s=>s.trim()).filter(Boolean),analysis:val('analysis'),notes:val('notes'),version:val('version'),featured:form.elements.namedItem('featured').checked,source:{author:val('author'),platform:val('platform'),url:val('source_url'),author_url:val('author_url'),date:val('source_date')},media:copy,assets};}
  function smallPreview(){const v=collect();$('#mini-media').innerHTML=v.media.thumbnail?`<img src="${esc(v.media.thumbnail)}" alt="内容封面">`:'封面预览';$('#mini-title').textContent=v.title||'内容标题';$('#mini-desc').textContent=v.subtitle||'一句话介绍会显示在这里';}
  function mark(){dirty=true;$('#save-state').textContent='有未保存的修改';smallPreview();}
  function assetList(){const images=media.images||[];$('#assets').innerHTML=images.map((u,i)=>`<div class="asset-row"><span>图片 ${i+1}</span><a href="${esc(u)}" target="_blank" rel="noopener">查看图片 ↗</a><button type="button" data-remove-image="${i}" aria-label="移除图片 ${i+1}">移除</button></div>`).join('')+assets.map((a,i)=>`<div class="asset-row"><span>附件</span><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.name)}</a><button type="button" data-remove="${i}" aria-label="移除附件 ${esc(a.name)}">移除</button></div>`).join('');$('#assets').querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{assets.splice(Number(b.dataset.remove),1);mark();assetList();});$('#assets').querySelectorAll('[data-remove-image]').forEach(b=>b.onclick=()=>{const removed=media.images.splice(Number(b.dataset.removeImage),1)[0];if(val('thumbnail')===removed)form.elements.namedItem('thumbnail').value=media.images[0]||'';mark();assetList();});}
  form.addEventListener('input',mark);form.addEventListener('change',mark);window.CMSSelect.enhance(form.elements.namedItem('type'),'内容类型',true);smallPreview();assetList();
  $('#preview').onclick=()=>preview({...c,...collect()});
  async function save(submit){
    if(busy||uploading)return;
    busy=true;$('#editor-error').textContent='';form.querySelectorAll('button').forEach(b=>b.disabled=true);$('#save-state').textContent='正在保存…';
    try{
      const payload=collect();
      // A clean pending item should be reviewed, not silently reset to a draft.
      if(!c.id||dirty){c=c.id?await api('/api/admin/cases/'+c.id,{method:'PUT',body:JSON.stringify({...payload,_version:c._version||0})}):await post('/api/admin/cases',payload);}
      dirty=false;replaceURL('/cms/edit/'+c.id);
      if(submit&&c.status!=='pending')c=await post('/api/admin/cases/'+c.id+'/submit',{_version:c._version||0});
      toast(submit?'已提交审核，确认发布后即可公开浏览':'草稿已保存');busy=false;await render();
    }catch(err){$('#editor-error').textContent=err.message;$('#save-state').textContent=dirty?'保存未完成':c.id?'草稿已保存，提交未完成':'保存未完成';$('#editor-error').scrollIntoView({block:'center',behavior:'smooth'});}
    finally{busy=false;form.querySelectorAll('button').forEach(b=>b.disabled=false);}
  }
  form.onsubmit=e=>{e.preventDefault();save(false);};$('#submit').onclick=()=>save(true);
  if($('#editor-approve'))$('#editor-approve').onclick=()=>{if(dirty)return toast('请先保存并重新提交修改，再审核发布');action(c,'approve');};
  if($('#editor-delete'))$('#editor-delete').onclick=()=>action(c,'delete');
  if($('#editor-reject'))$('#editor-reject').onclick=()=>{if(dirty)return toast('请先保存修改');action(c,'reject');};
  form.querySelectorAll('[data-upload]').forEach(b=>b.onclick=()=>{
    const kind=b.dataset.upload,input=document.createElement('input');input.type='file';input.accept=kind==='video'?'.mp4,.mov,.webm':kind==='attachment'?'.md,.txt,.pdf':'.jpg,.jpeg,.png,.webp';
    input.onchange=async()=>{const file=input.files[0];if(!file)return;const limit=kind==='video'?200:20;if(file.size>limit*1024*1024)return toast(`文件不能超过 ${limit} MB`);uploading++;busy=true;form.querySelectorAll('button').forEach(b=>b.disabled=true);$('#upload-status').textContent=`正在上传并处理 ${file.name}…${kind==='video'?'视频处理可能需要一些时间。':''}`;try{const r=await api('/api/admin/uploads',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Upload-Kind':kind,'X-File-Name':encodeURIComponent(file.name)},body:file});if(kind==='video'){media=r.media;form.elements.namedItem('video').value=media.video;form.elements.namedItem('thumbnail').value=media.thumbnail;}else if(kind==='attachment')assets.push({name:r.name,url:r.url});else{if(kind==='image')media.images=[...(media.images||[]),r.url];if(kind==='cover'||!val('thumbnail'))form.elements.namedItem('thumbnail').value=r.url;}mark();assetList();$('#upload-status').textContent='素材已上传，保存内容后生效';}catch(err){$('#upload-status').textContent=err.message;}finally{uploading--;busy=false;form.querySelectorAll('button').forEach(b=>b.disabled=false);}};
    input.click();
  });
}
function settings(){
  $('#main').innerHTML=`<div class="page-head"><div><div class="eyebrow">ACCOUNT SETTINGS</div><h1>账号设置</h1><p>管理内容工作台的访问密码。</p></div></div><form class="section settings"><h2>修改管理密码</h2><p>使用至少 12 个字符。修改后，所有已登录的会话都需要重新登录。</p>${field('current','当前密码','','','password')}${field('next','新密码','','至少 12 个字符','password')}${field('confirm','再次输入新密码','','','password')}<div class="error" role="alert"></div><button class="btn primary" type="submit">更新密码</button></form>`;
  const form=$('.settings');for(const input of form.querySelectorAll('input')){input.required=true;input.maxLength=256;input.autocomplete=input.name==='current'?'current-password':'new-password';if(input.name!=='current')input.minLength=12;}
  form.onsubmit=async e=>{e.preventDefault();const values=new FormData(form);if(values.get('next')!==values.get('confirm'))return $('.error',form).textContent='两次输入的新密码不一致';if(busy)return;busy=true;const b=$('[type=submit]',form);b.disabled=true;try{await post('/api/auth/password',{current_password:values.get('current'),new_password:values.get('next')});toast('密码已更新，请重新登录');login();}catch(err){$('.error',form).textContent=err.message;}finally{busy=false;b.disabled=false;}};
}
return {element:root,refreshCounts,render:()=>{active=true;return render();},deactivate,canLeave:()=>!active||leave(),prepareNavigation:()=>{dirty=false;}};
}

const {icon} = window.VisionSite;
/* The directory publishes on save; case review and drafts live in their own workflow. */
export function directoryManager(main, db, {esc, dialog, post, toast, markBusy, markDirty, reload}) {
  const $ = (s, el=main) => el.querySelector(s);
  let tab='entry', cat='', search='', limit=40, observer=null, frame=0;
  main.innerHTML = `<div class="page-head"><div><h1>AI 导航</h1><p>管理工具入口与分类，保存后对本机访客生效。</p></div><a href="/tools/ai-nav" data-link class="btn">查看导航 ${icon('external')}</a></div>
    <section class="panel"><div class="filters"><div class="tabs"><button class="tab" data-tab="entry">工具入口</button><button class="tab" data-tab="category">分类管理</button></div><button class="btn primary" data-new></button></div>
    <div class="filters"><span data-directory-filter><select id="directory-filter" aria-label="筛选目录分类"></select></span><div class="search"><input type="search" aria-label="搜索目录" placeholder="搜索名称、简介或网址"></div></div>
    <div class="directory-list"></div><div class="load-status"></div></section>`;
  const filter = $('select'), results = $('.directory-list');
  const refreshFilter = window.VisionMenu.enhanceSelect(filter,'筛选目录分类');
  function filtered() {
    const q = search.trim().toLowerCase();
    return tab==='category' ? db.categories.filter(c=>c.name.toLowerCase().includes(q)) :
      db.entries.filter(x=>(!cat||x.category===cat)&&[x.name,x.description,x.url].some(v=>v?.toLowerCase().includes(q)));
  }
  function draw() {
    const rows = filtered(), isGroup = tab==='category';
    main.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('on',b.dataset.tab===tab);b.setAttribute('aria-pressed',String(b.dataset.tab===tab));});
    $('[data-new]').innerHTML = `${icon('plus')} ${isGroup?'新建分类':'新建入口'}`;
    $('[data-directory-filter]').hidden=isGroup;
    filter.innerHTML='<option value="">全部分类</option>'+db.categories.map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('');
    filter.value=cat;refreshFilter();
    results.innerHTML=rows.slice(0,limit).map(rowHTML).join('') || '<div class="empty"><b>没有匹配的记录</b></div>';
    progress(rows);
  }
  function rowHTML(x){
      const isGroup=tab==='category', groups=new Map(db.categories.map(c=>[c.id,c.name]));
      const note=isGroup?`${db.entries.filter(e=>e.category===x.id).length} 个入口`:groups.get(x.category);
      return `<div class="directory-row" data-id="${esc(x.id)}"><div><strong>${esc(x.name)}</strong><span class="hint">${esc(note)}${!isGroup && x.description?' · '+esc(x.description):''}</span>${isGroup?'':`<a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">${esc(x.url)} ${icon('external')}</a>`}</div><div class="row-actions">${isGroup?'':`<button class="btn small" data-feature aria-pressed="${!!x.featured}">${x.featured?'已推荐':'推荐'}</button>`}<button class="btn small" data-edit>编辑</button><button class="btn small danger" data-delete>删除</button></div></div>`;
  }
  const sentinel=$('.load-status');
  function progress(rows){
    observer?.unobserve(sentinel);
    cancelAnimationFrame(frame);
    const shown=Math.min(rows.length,limit);
    sentinel.innerHTML=`<span>已显示 ${shown} / ${rows.length} 条</span>${shown<rows.length?'<button class="btn small" data-more>加载更多</button>':'<span>已全部加载</span>'}`;
    if(shown<rows.length && observer)frame=requestAnimationFrame(()=>observer?.observe(sentinel));
  }
  function more(){
    const rows=filtered(), next=limit+40;
    results.insertAdjacentHTML('beforeend',rows.slice(limit,next).map(rowHTML).join(''));
    limit=next;progress(rows);
  }
  if ('IntersectionObserver' in window) observer=new IntersectionObserver(changes=>{
    if(main.isConnected && changes.some(x=>x.isIntersecting) && limit<filtered().length) more();
  },{rootMargin:'0px 0px 160px'});
  async function feature(item,b){
    if(!markBusy(true))return;
    b.disabled=true;
    try{
      db=await post('/api/admin/ai-directory',{kind:'entry',action:'feature',id:item.id,featured:!item.featured,version:db.version});
      draw();toast(item.featured?'已取消推荐':'已加入顶部推荐');
      results.querySelector(`[data-id="${CSS.escape(item.id)}"] [data-feature]`)?.focus({preventScroll:true});
    }catch(err){toast(err.message);if([401,409].includes(err.status))reload();}
    finally{b.disabled=false;markBusy(false);}
  }
  function open(item, remove) {
    const kind=tab, isGroup=kind==='category', label=isGroup?'分类':'入口';
    if(remove && isGroup && db.entries.some(x=>x.category===item.id)){toast('请先移动或删除该分类中的入口');return;}
    if(!remove && !isGroup && !db.categories.length){toast('请先在「分类管理」中新建分类');return;}
    const field=(key,title,value='',options='')=>`<label class="field"><span>${title}</span><input name="${key}" value="${esc(value)}" ${options}></label>`;
    const title=`${remove?'删除':item?'编辑':'新建'}${label}`;
    const html=remove?`<p>确认删除「${esc(item.name)}」？保存后立即从导航移除，无法在平台内恢复。</p>`:
      field('name','名称',item?.name,'required maxlength="160"')+(isGroup?'':`
      <label class="field"><span>分类</span><select name="category" required>${db.categories.map(c=>`<option value="${esc(c.id)}" ${c.id===(item?.category||cat)?'selected':''}>${esc(c.name)}</option>`).join('')}</select></label>
      ${field('url','目标网址',item?.url,'required type="url" placeholder="https://…"')}
      ${field('description','用途简介',item?.description,'maxlength="500"')}
      ${field('heat','热度分（选填）',item?.heat,'type="number" min="0" max="2147483647" step="1"')}
      ${field('icon','图标地址（选填）',item?.icon,'placeholder="https://…"')}`);
    const d=dialog(`<form><h2>${title}</h2>${html}<div class="error" role="alert"></div><div class="dialog-actions"><button type="button" class="btn" data-close>取消</button><button type="submit" class="btn ${remove?'danger':'primary'}">${remove?'确认删除':'保存并生效'}</button></div></form>`);
    d.addEventListener('input',()=>markDirty(true));
    d.addEventListener('close',()=>markDirty(false),{once:true});
    const form=$('form',d);
    if(form.elements.category) window.VisionMenu.enhanceSelect(form.elements.category,'选择入口分类',true);
    form.onsubmit=async e=>{
      e.preventDefault();if(!markBusy(true))return;
      d.dataset.working='true';d.querySelectorAll('button').forEach(b=>b.disabled=true);
      try {
        const payload=Object.fromEntries(new FormData(form));
        if ('heat' in payload) payload.heat = payload.heat === '' ? null : Number(payload.heat);
        db=await post('/api/admin/ai-directory',{...payload,id:item?.id,kind,action:remove?'delete':'save',version:db.version});
        markDirty(false);d.close();draw();toast(remove?'已从导航删除':'已保存，导航已更新');
      }catch(err){
        $('.error',d).textContent=err.message;
        if(err.status===409) {
          const refresh=document.createElement('button');refresh.type='button';refresh.className='btn small';refresh.textContent='重新加载目录';
          refresh.onclick=()=>{markDirty(false);d.close();reload();};$('.error',d).append(' ', refresh);
        }else if(err.status===401){markDirty(false);d.close();reload();}
      }finally{delete d.dataset.working;d.querySelectorAll('button').forEach(b=>b.disabled=false);markBusy(false);}
    };
  }
  main.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    if(b.hasAttribute('data-tab')){tab=b.dataset.tab;limit=40;draw();}
    else if(b.hasAttribute('data-more'))more();
    else if(b.hasAttribute('data-new'))open(null,false);
    else if(b.closest('[data-id]')){
      const item=filtered().find(x=>x.id===b.closest('[data-id]').dataset.id);
      if(item && b.hasAttribute('data-feature'))feature(item,b);
      else if(item)open(item,b.hasAttribute('data-delete'));
    }
  });
  filter.onchange=()=>{cat=filter.value;limit=40;draw();};
  $('input[type=search]').oninput=e=>{search=e.target.value;limit=40;draw();};
  draw();
  return ()=>{cancelAnimationFrame(frame);observer?.disconnect();observer=null;};
}

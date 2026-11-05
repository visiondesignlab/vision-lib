const labels={queued:'等待本机处理',review:'待核对分类',needs_video:'待补视频',linked:'已入库',duplicate:'已有相同来源',archived:'已归档'};
const types={video:'AI 视频案例',showcase:'灵感库'};

export function submissionManager(main,{api,post,esc,dialog,toast,upload}) {
  let timer, stopped=false, busy=false;
  main.innerHTML='<div class="page-head"><div><h1>作品投稿</h1><p>本地与 Pages 的私密投稿在这里汇总，收录后进入审核队列。</p></div>' +
    '<button class="btn" type="button" data-sync>同步线上投稿</button></div><p role="status" class="hint"></p><div class="submission-list"></div>';
  const list=main.querySelector('.submission-list'), status=main.querySelector('[role=status]'), sync=main.querySelector('[data-sync]');
  async function refresh() {
    const db=await api('/api/admin/submissions');
    if(stopped) return;
    status.textContent='共 '+db.items.length+' 条 · '+(db.connected?'已配置线上同步':'当前仅接收本地投稿');
    sync.disabled=busy || !db.connected;
    const focused=list.contains(document.activeElement)?document.activeElement.closest('[data-review]')?.dataset.review:null;
    list.innerHTML=db.items.map(item=>'<article><div><strong>'+esc(item.title || item.source_title || '未命名作品')+
      '</strong><span class="badge">'+esc(labels[item.status])+'</span></div><a href="'+esc(item.url)+'" rel="noreferrer" target="_blank">'+esc(item.url)+'</a>'+
      '<small>'+esc(item.origin==='pages'?'Pages 投稿':'本地投稿')+' · '+esc(item.created)+' · '+esc(types[item.target]||'待判定')+'</small>'+
      (item.note?'<p>'+esc(item.note)+'</p>':'')+(item.reason?'<p>'+esc(item.reason)+'</p>':'')+(item.problem?'<p>'+esc(item.problem)+'</p>':'')+
      (item.case_id?(item.case_status?'<a class="btn small" data-nav href="/cms/edit/'+encodeURIComponent(item.case_id)+'">打开内容</a>':'<small>关联内容已删除</small>'):
        '<button type="button" class="btn small" data-review="'+esc(item.id)+'">处理投稿</button>')+'</article>').join('') ||
      '<div class="empty"><b>还没有投稿</b></div>';
    list.querySelectorAll('[data-review]').forEach(b=>b.onclick=()=>edit(db.items.find(i=>i.id===b.dataset.review)));
    if(focused) list.querySelector('[data-review="'+CSS.escape(focused)+'"]')?.focus({preventScroll:true});
  }
  function edit(item) {
    const d=dialog('<form><h2>处理投稿</h2><p>'+esc(item.title || item.url)+'</p><label class="field"><span>目标栏目</span><select name="target">'+
      '<option value="">按制作证据自动判断</option>'+Object.entries(types).map(([k,v])=>'<option value="'+k+'">'+v+'</option>').join('')+
      '</select></label><label class="field"><span>补传原片（可选）</span><input name="video" type="file" accept=".mp4,.mov,.webm"></label>'+
      '<p role="alert"></p><div class="dialog-actions"><button type="button" class="btn" data-close>取消</button><button type="button" class="btn" data-archive>归档</button>'+
      '<button type="submit" class="btn primary">开始处理</button></div></form>');
    const form=d.querySelector('form');
    form.elements.target.value=item.override || '';
    window.VisionMenu.enhanceSelect(form.elements.target,'目标栏目',true);
    async function save(action) {
      if(busy)return;
      busy=true;d.dataset.working='true';form.inert=true;
      const error=form.querySelector('[role=alert]');
      try {
        let attachment='';
        if(action==='process' && form.elements.video.files.length) {
          error.textContent='正在处理视频…';
          const result=await upload(form.elements.video.files[0]); attachment=result.media.video;
        }
        await post('/api/admin/submissions/'+item.id,{action,version:item.version,target:form.elements.target.value,attachment});
        d.close();await refresh();
      } catch(err){error.textContent=err.message;}
      finally {busy=false;form.inert=false;delete d.dataset.working;}
    }
    form.onsubmit=e=>{e.preventDefault();save('process');};
    d.querySelector('[data-archive]').onclick=()=>save('archive');
  }
  sync.onclick=async()=>{
    if(busy)return;
    busy=true;sync.disabled=true;
    try {const result=await post('/api/admin/submissions/sync');toast('同步完成，收到 '+result.received+' 条投稿');}
    catch(err){toast(err.message);}
    finally {busy=false;refresh().catch(err=>toast(err.message));}
  };
  async function poll(){
    try {if(!busy && !document.hidden && !main.closest('.cms-body')?.querySelector('dialog[open]'))await refresh();}
    catch(err){if(!stopped)status.textContent=err.message;}
    if(!stopped)timer=setTimeout(poll,4000);
  }
  poll();
  return ()=>{stopped=true;clearTimeout(timer);};
}

const {staticMode} = window.VisionSite;

export function submissionPage() {
  const page = document.createElement('section');
  page.className = 'submission-page';
  const relay = window.VISION_CONFIG?.intakeUrl;
  const connected = !staticMode || !!relay;
  page.innerHTML = '<header class="head"><h1>提交作品</h1><span class="sub">分享一支值得收录的视频。</span></header>' +
    '<form class="submission-form"><p>只有管理员可查看投稿，作品审核通过后才会公开。</p>' +
    '<label>作品链接 <input type="url" name="url" required maxlength="2048" placeholder="https://" autocomplete="url"></label>' +
    '<label>作品名称 <span>选填</span><input name="title" maxlength="160"></label>' +
    '<label>制作线索 <span>选填</span><textarea name="note" rows="3" maxlength="1600" placeholder="例如作者提到的生成工具、实拍方式或幕后资料"></textarea></label>' +
    '<div role="status" class="submission-status"></div><button class="pill-btn dark" type="submit">提交作品</button></form>';
  const form = page.querySelector('form'), status = page.querySelector('[role=status]'), button = form.querySelector('button');
  let id, lastPayload;
  if (!connected) { button.disabled = true; status.textContent = '线上私密收件服务尚未接通。'; }
  form.onsubmit = async e => {
    e.preventDefault();
    if (!connected || button.disabled) return;
    const fields = Object.fromEntries(new FormData(form)), url = new URL(fields.url);
    if (!['http:','https:'].includes(url.protocol) || url.username || url.password) {
      status.textContent = '请填写完整的公开作品链接。'; return;
    }
    const payload = JSON.stringify(fields);
    if (payload!==lastPayload) {
      id=Array.from(crypto.getRandomValues(new Uint8Array(16)), byte=>byte.toString(16).padStart(2,'0')).join('');
      lastPayload=payload;
    }
    button.disabled=true; status.textContent='正在提交…';
    try {
      const endpoint = staticMode ? relay.replace(/\/$/,'')+'/submissions' : '/api/submissions';
      const response = await fetch(endpoint, {method:'POST',credentials:'omit',referrerPolicy:'no-referrer',
        headers:{'Content-Type':'application/json'},body:JSON.stringify({id,...fields})});
      if (response.status===404) throw Error('投稿接口暂时不可用，请稍后重试。');
      const result = await response.json();
      if (!response.ok || result.receipt!==id) throw Error(result.error || '提交失败');
      form.hidden=true;
      const receipt=document.createElement('div');
      receipt.className='submission-form';receipt.setAttribute('role','status');
      receipt.innerHTML='<h2>已收到投稿</h2><p></p><small></small><button type="button" class="pill-btn shadow">再提交一条</button>';
      receipt.querySelector('p').textContent=fields.url;
      receipt.querySelector('small').textContent='回执编号 '+result.receipt;
      receipt.querySelector('button').onclick=()=>{receipt.remove();form.reset();lastPayload=null;
        status.textContent='';form.hidden=false;form.elements.url.focus();};
      page.append(receipt);
    } catch (err) {status.textContent=err.message==='Failed to fetch'?'暂时无法连接收件服务，请稍后重试。':err.message;}
    finally {button.disabled=false;}
  };
  return page;
}

export function analysisSection(report) {
  if (!report?.shots?.length) return '';
  const escape = value => String(value || '').replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const rows = report.shots.map((shot,i)=>{
    const frame=shot.frame ? '<img loading="lazy" alt="镜头 '+(i+1)+' 关键帧" src="'+escape(shot.frame)+'">' : '';
    return '<tr><th scope="row">'+(i+1)+'</th><td>'+Number(shot.start).toFixed(2)+' – '+Number(shot.end).toFixed(2)+
      ' s</td><td>'+frame+escape(shot.camera)+'</td></tr>';
  }).join('');
  return '<section class="sec shot-report"><h4>镜头分析</h4><p>'+Number(report.duration).toFixed(1)+' 秒 · '+report.shots.length+
    ' 个镜头</p>'+(report.observation?'<p>'+escape(report.observation)+'</p>':'')+
    '<details open><summary>查看实测镜头表</summary><div><table><thead><tr><th>镜号</th><th>时间码</th><th>关键帧 / 估算运动</th></tr></thead><tbody>'+
    rows+'</tbody></table></div></details></section>';
}

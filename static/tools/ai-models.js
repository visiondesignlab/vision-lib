import {toolSearch} from './tool-search.js';
const {path} = window.VisionSite;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const modes = {
  language:['语言模型','语言模型智能指数'],
  image:['图像','文生图 Elo'],
  video:['视频','文生视频 Elo（含音频）'],
  speech:['语音','文本转语音 Elo（原生音色）'],
};
const languageColumns = [
  {key:'contextTokens',label:'上下文窗口',group:'功能',unit:'Tokens',desc:true},
  {key:'provider',label:'开发商',group:'功能'},
  {key:'score',label:'智能指数',group:'智能',desc:true,title:'Artificial Analysis Intelligence Index'},
  {key:'costUSD',label:'每任务成本',group:'价格',unit:'美元'},
  {key:'durationMinutes',label:'每任务耗时',group:'速度',unit:'分钟'},
  {key:'firstAnswerSeconds',label:'首个答案 Token',group:'延迟',unit:'秒'},
];
const collator = new Intl.Collator('zh-CN',{numeric:true});
const tokenCount = new Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:2});
const integers = new Intl.NumberFormat('en');
const normalize = value => (value || '').toLowerCase().replace(/\s+/g,'');
const modelMarks = [
  [/^(Gemini|Nano Banana|Veo)/i,'gemini-color'], [/^Claude/i,'claude-color'],
  [/^(GPT|Sora)/i,'openai'], [/^Muse/i,'muse-color'], [/^Kimi/i,'kimi-color'],
  [/^Grok/i,'grok'], [/^(Qwen|Wan)/i,'qwen-color'], [/^DeepSeek/i,'deepseek-color'],
  [/^GLM/i,'zai'], [/^(MiMo|Xiaomi)/i,'xiaomimimo'], [/^(Kling|可灵)/i,'kling-color'],
  [/^Hailuo/i,'hailuo-color'], [/^Imagen/i,'google-color'], [/^Flux/i,'flux'],
];
const sortByMode = new Map();
let dataRequest;
export function loadModels() {
  if (!dataRequest) dataRequest = fetch(path('/static/tools/model-rankings.json'),{cache:'no-cache'})
    .then(res=>{ if (!res.ok) throw new Error('无法读取排行榜'); return res.json(); })
    .catch(err=>{ dataRequest = null; throw err; });
  return dataRequest;
}
function columnsFor(mode) {
  const leading = [{key:'rank',label:'排名'},{key:'model',label:'模型'}];
  if (mode === 'language') return leading.concat(languageColumns);
  const cols = [
    {key:'provider',label:'开发商',group:'模型信息'},
    {key:'score',label:'Elo',group:'质量',desc:true},
    {key:'votes',label:'样本数',group:'质量',desc:true},
    {key:'released',label:'发布日期',group:'模型信息',desc:true},
  ];
  if (mode === 'speech') cols.push({key:'voices',label:'音色数',group:'模型信息',desc:true});
  cols.push({key:'price',label:'价格',group:'成本',unit:{image:'美元 / 千张',video:'美元 / 分钟',speech:'美元 / 百万字符'}[mode]});
  return leading.concat(cols);
}
function identity(text, logo) {
  const img = logo ? `<img src="${esc(path('/static/tools/ranking-logos/'+logo))}" width="18" height="18" alt="">` : '';
  return `<span class="rank-identity">${img}<span>${esc(text)}</span></span>`;
}
function cell(row, column, logos) {
  const key = column.key, value = row[key];
  if (value == null) return '<span class="model-missing" aria-label="暂无数据">—</span>';
  switch (key) {
    case 'model': {
      const mark=modelMarks.find(([pattern])=>pattern.test(value));
      const label=identity(value,mark ? mark[1]+'.svg' : logos[row.provider]);
      return row.url ? `<a href="${esc(row.url)}" target="_blank" rel="noopener noreferrer">${label}</a>` : label;
    }
    case 'provider': return identity(value,logos[value]);
    case 'contextTokens': return tokenCount.format(value);
    case 'votes': return integers.format(value);
    case 'price': case 'costUSD': return '$'+value.toFixed(2);
    case 'durationMinutes': return value.toFixed(1);
    case 'firstAnswerSeconds': return value.toFixed(2);
    default: return esc(value);
  }
}
function header(col, rowspan=1) {
  const title=col.title ? ` title="${esc(col.title)}"` : '';
  const unit=col.unit ? `<small>${esc(col.unit)}</small>` : '';
  return `<th scope="col" rowspan="${rowspan}" data-column="${col.key}"><button type="button" data-rank-sort="${col.key}"${title}><span>${col.label}${unit}</span><i aria-hidden="true"></i></button></th>`;
}
function tableHead(cols) {
  const groups=[];
  for(const col of cols.slice(2)){
    if(groups.at(-1)?.label===col.group) groups.at(-1).span++;
    else groups.push({label:col.group,span:1});
  }
  return `<tr>${cols.slice(0,2).map(c=>header(c,2)).join('')}${groups.map(g=>`<th scope="colgroup" colspan="${g.span}">${g.label}</th>`).join('')}</tr><tr>${cols.slice(2).map(c=>header(c)).join('')}</tr>`;
}
function sortRows(rows, {key,direction}) {
  return rows.sort((a,b)=>{
    const left=a[key], right=b[key];
    if(left==null || right==null) return (left==null)-(right==null) || a.rank-b.rank;
    const result=typeof left==='string'?collator.compare(left,right):left-right;
    return (direction==='descending'?-result:result) || a.rank-b.rank;
  });
}

export function modelsPage(dataset, replaceURL) {
  const params=new URL(location.href).searchParams;
  const selected=params.get('type');
  const mode=Object.hasOwn(modes,selected)?selected:'language';
  const board=dataset.boards[mode], cols=columnsFor(mode);
  const original=board.rows.map((r,i)=>({...r,rank:i+1}));
  let sort=sortByMode.get(mode) || {key:'score',direction:'descending'};
  const page=document.createElement('section');
  page.className='models-page';
  const tabLinks=Object.entries(modes).map(([key,[label]])=>{
    const href=path('/tools/ai-models')+(key==='language'?'':'?type='+key);
    return `<a data-link href="${href}"${key===mode?' aria-current="page"':''}>${label}</a>`;
  }).join('');
  page.innerHTML=`<header class="models-header"><h1>AI 大模型</h1><span>${dataset.date} 快照</span><a href="${esc(board.source)}" target="_blank" rel="noopener noreferrer">Artificial Analysis ↗</a></header>
    <div class="models-tools"><nav class="model-tabs" aria-label="榜单类型">${tabLinks}</nav><div data-search-slot></div></div>
    <div class="ai-ranking"><div class="ai-ranking-head"><h2>${modes[mode][1]}</h2><span class="models-count" role="status"></span></div>
    <div class="ai-ranking-scroll" role="region" tabindex="0" aria-label="模型排行，可上下或左右滚动"><table aria-label="${modes[mode][1]}"><thead>${tableHead(cols)}</thead><tbody></tbody></table></div></div>`;
  const search=toolSearch('搜索模型或开发商','搜索模型或开发商',params.get('q'),()=>{
    const url=new URL(location.href), term=search.input.value.trim();
    if(term)url.searchParams.set('q',term);else url.searchParams.delete('q');
    replaceURL(url);
    draw();
    page.querySelector(".ai-ranking-scroll").scrollTop=0;
  });
  page.querySelector('[data-search-slot]').replaceWith(search.field);
  function draw(){
    const q=normalize(search.input.value);
    const rows=sortRows(original.filter(r=>normalize(r.model+' '+r.provider).includes(q)),sort);
    page.querySelector('.models-count').textContent=q?`${rows.length} / ${original.length} 个模型`:`${original.length} 个模型`;
    page.querySelector('tbody').innerHTML=rows.map(row=>`<tr>${cols.map(col=>col.key==='model'?`<th scope="row">${cell(row,col,dataset.providerLogos)}</th>`:`<td data-key="${col.key}">${cell(row,col,dataset.providerLogos)}</td>`).join('')}</tr>`).join('') || `<tr><td colspan="${cols.length}" class="models-empty">没有匹配的模型</td></tr>`;
    page.querySelector('th[aria-sort]')?.removeAttribute('aria-sort');
    page.querySelector(`th[data-column="${sort.key}"]`).setAttribute('aria-sort',sort.direction);
  }
  page.querySelector('thead').addEventListener('click',event=>{
    const button=event.target.closest('[data-rank-sort]');
    if(!button)return;
    const col=cols.find(c=>c.key===button.dataset.rankSort);
    const descending=sort.key===col.key?sort.direction==='ascending':col.desc;
    sort={key:col.key,direction:descending?'descending':'ascending'};
    sortByMode.set(mode,sort);
    draw();
    page.querySelector(".ai-ranking-scroll").scrollTop=0;
  });
  draw();
  return page;
}

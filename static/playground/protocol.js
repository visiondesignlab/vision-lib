// Shared by the browser and the generation service. Catalog is installed once on each side.
let models=[];
export function setCatalog(list){models=list;}
export function getModel(id){const model=models.find(m=>m.id===id);if(!model)throw Error('请选择有效模型');return model;}
export const roleNames={start:'首帧',end:'尾帧',reference:'参考图片',video:'参考视频',audio:'参考音频'};
export const settingNames={aspectRatio:'画面比例',resolution:'分辨率',duration:'时长（秒）',batchSize:'生成数量',enhancePrompt:'优化提示词',generateAudio:'生成音频',outputFormat:'文件格式',sound:'生成音频',cfgScale:'提示词遵循度',multiShots:'多镜头',keepOriginalSound:'保留原声',characterOrientation:'动作方向'};
export function publicURL(value){
  try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password&&u.hostname.includes('.')&&!/^(localhost|127\.|0\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)/.test(u.hostname)&&!u.hostname.startsWith('[')&&! /\.(local|internal|localhost)$/.test(u.hostname)?u.href:null;}catch{return null;}
}
export function validatePlane(raw){
  if(!raw||typeof raw!=='object')throw Error('生成参数无效');
  const model=getModel(raw.model),text=raw.prompt?.text;
  if(typeof text!=='string'||!text.trim()||text.length>12000)throw Error('请输入提示词，最多 12000 字符');
  const settings={};
  for(const [key,field] of Object.entries(model.settings)){
    const v=raw.settings?.[key]??field.default;
    if(field.type==='enum'&&!field.values.includes(v)||field.type==='boolean'&&typeof v!=='boolean'||field.type==='range'&&(typeof v!=='number'||!Number.isFinite(v)||v<field.min||v>field.max||Math.abs((v-field.min)/(field.step||1)-Math.round((v-field.min)/(field.step||1)))>1e-6))throw Error(`${settingNames[key]||key} 超出模型支持范围`);
    settings[key]=v;
  }
  const media={};
  for(const [role,items] of Object.entries(raw.media||{})){
    if(!Array.isArray(items)||items.length>(model.roles[role]||0))throw Error(`${roleNames[role]||'素材'} 数量超出模型限制`);
    media[role]=items.map(item=>{const url=publicURL(item.url);if(!url||url.length>8192)throw Error('素材需要可访问的 HTTPS 地址');return {url,role};});
  }
  if(media.end?.length&&!media.start?.length)throw Error('使用尾帧时，请先添加首帧');
  if(model.id.includes('motion')&&(!media.start?.length||!media.video?.length))throw Error('动作控制需要首帧和参考视频');
  if(['seedance-2.5-edit','seedance-2.5-extend'].includes(model.id)&&!media.video?.length)throw Error('请添加要编辑或延长的视频');
  if(model.paths&&!model.paths.text&&!Object.values(media).some(a=>a.length))throw Error('这个模型需要参考素材');
  return {model:model.id,prompt:{text:text.trim()},settings,media};
}

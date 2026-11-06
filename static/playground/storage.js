let opening;
function database(){
  return opening ||= new Promise((resolve,reject)=>{
    const request=indexedDB.open('vision-playground',1);
    request.onupgradeneeded=()=>request.result.createObjectStore('studio');
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(Error('浏览器存储不可用'));
  });
}
export async function read(key,fallback){
  const db=await database();return new Promise((resolve,reject)=>{
    const tx=db.transaction('studio'),r=tx.objectStore('studio').get(key);
    r.onsuccess=()=>resolve(r.result??fallback);r.onerror=()=>reject(r.error);
  });
}
export async function write(key,value){
  const db=await database();return new Promise((resolve,reject)=>{
    const tx=db.transaction('studio','readwrite');tx.objectStore('studio').put(value,key);
    tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);
  });
}

"""Cross-origin PDF loading must request validated ranges, never the full file."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PDFRangeTests(unittest.TestCase):
    def test_ranges_retry_and_reject_truncated_responses(self):
        script = r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const {airPDFRange}=await import('data:text/javascript;base64,'+fs.readFileSync(process.argv[1]).toString('base64'));
const calls=[];
let deliver,fail,attempt=0;
class PDFDataRangeTransport {
  constructor(length,data,done){this.length=length;assert.equal(done,true);}
  onDataRange(begin,chunk){deliver({begin,chunk});}
}
global.fetch=async(_href,options)=>{
  calls.push(options);
  if(options.method==='HEAD')return {ok:true,headers:new Headers({'Content-Length':'1000'})};
  assert.equal(options.headers.Range,'bytes=10-13');
  if(!attempt++)throw new Error('temporary failure');
  return {status:206,arrayBuffer:async()=>new Uint8Array([1,2,3,4]).buffer};
};
const controller=new AbortController();
const t=await airPDFRange({PDFDataRangeTransport},'https://air.example/sample.pdf',controller,e=>fail(e));
const received=new Promise(resolve=>deliver=resolve);t.requestDataRange(10,14);
const chunk=await received;assert.equal(t.length,1000);assert.equal(chunk.begin,10);assert.equal(chunk.chunk.length,4);
assert.equal(calls.length,3);
global.fetch=async()=>({status:206,arrayBuffer:async()=>new Uint8Array([1]).buffer});
const rejected=new Promise(resolve=>fail=resolve);t.requestDataRange(10,14);
assert.match((await rejected).message,/不完整/);
t.abort();assert.equal(controller.signal.aborted,true);
'''
        subprocess.run(['node', '--input-type=module', '-e', script, str(ROOT / 'static/assets/pdf-range.js')], check=True, timeout=10)

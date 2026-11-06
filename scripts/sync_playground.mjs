// Usage: node scripts/sync_playground.mjs /path/to/open-higgsfield
// Only the upstream model definitions and request mapping are imported; UI is native to Vision Lab.
import {readFile, writeFile, mkdir, readdir, mkdtemp, rm} from 'node:fs/promises';
import {stripTypeScriptTypes} from 'node:module';
import {execFileSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import {resolve, join} from 'node:path';
import {pathToFileURL} from 'node:url';
const source=resolve(process.argv[2] || ''), output=new URL('../static/playground/', import.meta.url);
const scratch=await mkdtemp(join(tmpdir(),'vision-models-'));
try {
  await mkdir(join(scratch,'catalog'));
  await writeFile(join(scratch,'package.json'),'{"type":"module"}');
  for(const name of await readdir(join(source,'src/generation/catalog'))) {
    if(!name.endsWith('.ts')) continue;
    const text=stripTypeScriptTypes(await readFile(join(source,'src/generation/catalog',name),'utf8'))
      .replace(/from "(\.\/[^"]+)"/g,(_,p)=>`from "${p}.js"`);
    await writeFile(join(scratch,'catalog',name.replace(/\.ts$/,'.js')),text);
  }
  const {MODELS}=await import(pathToFileURL(join(scratch,'catalog/index.js')));
  const commit=execFileSync('git',['-C',source,'rev-parse','HEAD'],{encoding:'utf8'}).trim();
  await mkdir(output,{recursive:true});
  await writeFile(new URL('catalog.json',output),JSON.stringify({source:'https://github.com/wide-trace/open-higgsfield',commit,models:MODELS},null,2)+'\n');
  const mapper=stripTypeScriptTypes(await readFile(join(source,'src/generation/to-platform.ts'),'utf8'))
    .replace(/import \{ getModel \} from "\.\/catalog";/,'import {getModel} from "./protocol.js";');
  await writeFile(new URL('mapper.js',output),'// Adapted from wide-trace/open-higgsfield @ '+commit+'; see NOTICE.md.\n'+mapper.replace(/[ \t]+$/gm,''));
  console.log(`${MODELS.length} models imported from ${commit}`);
} finally { await rm(scratch,{recursive:true,force:true}); }

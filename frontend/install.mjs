// The manifest is source; dependency installation is generated project State.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const root=path.dirname(fileURLToPath(import.meta.url));
const state=process.env.CALL_ASSISTANT_STATE||'/var/lib/openclaw/state/projects/call-assistant';
const target=path.join(state,'work/frontend-deps');
fs.mkdirSync(target,{recursive:true});
for(const name of ['package.json','package-lock.json']){
  const contents=fs.readFileSync(path.join(root,name),'utf8');
  JSON.parse(contents);
  fs.writeFileSync(path.join(target,name),contents);
}
const result=spawnSync('npm',['ci','--ignore-scripts','--no-audit','--no-fund'],{cwd:target,stdio:'inherit'});
process.exit(result.status??1);

// Producer-owned generated build artifacts belong in State, not source.
import {createRequire} from 'node:module';import {spawnSync} from 'node:child_process';import fs from 'node:fs';import path from 'node:path';
const state=process.env.CALL_ASSISTANT_STATE||'/var/lib/openclaw/state/projects/call-assistant';const root=path.dirname(new URL(import.meta.url).pathname);
const deps=path.join(state,'work/frontend-deps');const req=createRequire(path.join(deps,'package.json'));
const config={compilerOptions:{target:'ES2022',lib:['ES2022','DOM'],module:'ESNext',moduleResolution:'Bundler',jsx:'react-jsx',strict:true,skipLibCheck:true,noEmit:true,esModuleInterop:true,allowSyntheticDefaultImports:true,baseUrl:path.join(deps,'node_modules'),paths:{react:['@types/react'],'react/jsx-runtime':['@types/react/jsx-runtime.d.ts'],'react-dom/client':['@types/react-dom/client.d.ts']},typeRoots:[path.join(deps,'node_modules/@types')]},files:[path.join(root,'app.tsx')]};
const conf=path.join(state,'work/tsconfig.json');fs.writeFileSync(conf,JSON.stringify(config));
const vitePackage=req.resolve('vite/package.json');const viteBin=JSON.parse(fs.readFileSync(vitePackage,'utf8')).bin.vite;
for(const args of [[req.resolve('typescript/bin/tsc'),'--project',conf],[path.join(path.dirname(vitePackage),viteBin),'build','--config',path.join(root,'vite.config.mjs')]]){const r=spawnSync(process.execPath,args,{stdio:'inherit',env:process.env});if(r.status!==0)process.exit(r.status||1);}

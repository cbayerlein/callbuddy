// Authorized import from the already-open AI Studio key details dialog.
// No credential is returned to model context, clipboard, logs, or command args.
const {chromium}=require(require.resolve('playwright',{paths:['/root/openclaw']}));
const fs=require('node:fs');
async function main(){
  const browser=await chromium.connectOverCDP('http://127.0.0.1:9222');
  try{
    const page=browser.contexts()[0].pages().find(p=>p.url()==='https://aistudio.google.com/api-keys');
    if(!page)throw Error('Authorized AI Studio tab missing');
    const key=await page.evaluate(()=>{
      const text=document.body.innerText;
      if(!text.includes('API key details')||!text.includes('Default Gemini API Key'))throw Error('Expected key dialog missing');
      const key=text.match(/AIza[A-Za-z0-9_-]{35}/)?.[0];
      if(!key)throw Error('No visible credential in expected dialog');
      return key;
    });
    const path='/var/lib/openclaw/state/credentials/google-gemini.json';
    if(fs.existsSync(path)){
      if(JSON.parse(fs.readFileSync(path,'utf8')).api_key!==key)throw Error('Preserve existing different credential');
    }else fs.writeFileSync(path,JSON.stringify({api_key:key,source:'Authorized shared-browser AI Studio import',project:'gen-lang-client-0664213382',created_at:new Date().toISOString()}),{mode:0o600,flag:'wx'});
    await page.keyboard.press('Escape');
    console.log(JSON.stringify({credential_saved:true,created_key:false,secret_printed:false}));
  }finally{await browser.close();}
}
main().catch(e=>{console.error('Credential import failed: '+e.name);process.exitCode=1;});

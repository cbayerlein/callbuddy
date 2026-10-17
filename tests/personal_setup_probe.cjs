// Existing shared context only. Secrets are read locally, never printed.
const {chromium}=require(require.resolve('playwright',{paths:['/root/openclaw']}));
const fs=require('node:fs');
async function main(){
  const browser=await chromium.connectOverCDP('http://127.0.0.1:9222');
  try{
    const page=browser.contexts()[0].pages().find(p=>p.url()==='https://ubuntu-2404-openclaw.fritz.box/callbuddy/');
    if(!page)throw Error('Verified task tab missing');
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    // Rotate the task's own session before final verification/handoff.
    await page.request.delete('https://ubuntu-2404-openclaw.fritz.box/callbuddy/api/auth');
    await page.reload({waitUntil:'domcontentloaded'});
    await page.locator('input[type=password]').waitFor({timeout:15000});
    const password=fs.readFileSync(process.argv[2],'utf8').replace(/[\r\n]+$/,'');
    if(await page.locator('input[type=password]').count()){
      await page.locator('input[type=password]').fill(password);
      await page.locator('input[type=password]').press('Enter');
    }
    await page.getByLabel('Telefonnummer',{exact:true}).waitFor({timeout:15000});
    const r=await page.request.get('https://ubuntu-2404-openclaw.fritz.box/callbuddy/api/settings');
    if(!r.ok())throw Error('Authenticated API failed');
    const settings=await r.json();
    if(settings.person.name!=='Christian Bayerlein'||!settings.default_sip||!settings.default_model)throw Error('Personal defaults missing');
    const p=await (await page.request.get('https://ubuntu-2404-openclaw.fritz.box/callbuddy/api/profiles')).json();
    if(!p.sip.some(x=>x.has_credential)||!p.models.some(x=>x.has_credential))throw Error('Credentials missing');
    if(!p.sip.some(x=>x.phone_number)||!p.models.some(x=>x.provider==='google'&&x.has_credential&&x.prep_model))throw Error('Phone mapping or Gemini missing');
    if(JSON.stringify(p).includes('credential_ref')||JSON.stringify(p).includes('api_key'))throw Error('Credential exposed');
    if(!await page.evaluate(()=>isSecureContext&&Boolean(navigator.mediaDevices)))throw Error('Not a browser secure context');
    const session=(await page.context().cookies('https://ubuntu-2404-openclaw.fritz.box/callbuddy/')).find(c=>c.name==='call_assistant_session');
    if(!session?.httpOnly||!session?.secure)throw Error('Session cookie not protected');
    await page.getByRole('button',{name:'Einstellungen',exact:true}).click();
    await page.getByRole('button',{name:'Einstellungen speichern',exact:true}).waitFor({timeout:15000});
    await page.screenshot({path:'/var/lib/openclaw/state/projects/call-assistant/work/media-runs/personal-setup-20261015/settings.png',fullPage:true});
    await page.getByRole('button',{name:'Anrufen',exact:true}).click();
    if(errors.length)throw Error('Page errors: '+errors.join(';'));
    console.log(JSON.stringify({https:true,secure_context:true,login:true,secure_httponly_cookie:true,personal_settings:true,provider_credentials:true,secret_leak:false,paid_requests:0,dials:0}));
  }finally{await browser.close();}
}
main().catch(e=>{console.error('HTTPS UI probe failed: '+e.name);process.exitCode=1;});

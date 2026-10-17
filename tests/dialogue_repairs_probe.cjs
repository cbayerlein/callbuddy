// Existing shared browser context only; never creates a call or audio session.
const {chromium}=require(require.resolve('playwright',{paths:['/root/openclaw']}));
const fs=require('node:fs');
let stage='connect';
async function main(){
 const browser=await chromium.connectOverCDP('http://127.0.0.1:9222');
 try{
  const page=browser.contexts()[0].pages().find(p=>p.url()==='https://ubuntu-2404-openclaw.fritz.box/callbuddy/');
  if(!page)throw Error('CallBuddy handoff tab missing');
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.reload({waitUntil:'domcontentloaded'});
  stage='authenticate';
  const base='https://ubuntu-2404-openclaw.fritz.box/callbuddy/api/';
  const request=async(path,method='GET',body)=>page.evaluate(async({url,method,body})=>{
   const r=await fetch(url,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
   return {status:r.status,data:await r.json()};
  },{url:base+path,method,body});
  await request('auth','DELETE'); // Rotate the task-owned browser session.
  await page.reload({waitUntil:'domcontentloaded'});
  let response=await request('settings');
  if(response.status===401){
   await page.locator('input[type=password]').fill(fs.readFileSync(process.argv[2],'utf8').trimEnd());
   await page.locator('input[type=password]').press('Enter');
   await page.locator('input[type=password]').waitFor({state:'hidden'});
   response=await request('settings');
  }
  if(response.status!==200)throw Error('Settings access failed');
  stage='settings contract';
  const settings=response.data;
  if('call_budget_eur' in settings||settings.default_text_model!=='operator-text-openai')throw Error('New settings missing');
  await page.getByRole('button',{name:'Anrufen',exact:true}).click();
  stage='home UI';
  // The task tab may restore a real historical call or brief. Do not overwrite it.
  const home=await page.getByLabel('Dein Anliegen',{exact:true}).count();
  if(home){
   await page.getByLabel('Textmodell für die Vorabklärung',{exact:true}).waitFor();
   if(await page.getByLabel('Gesprächsszenario',{exact:true}).count())throw Error('Scenario selector remains');
   await page.getByLabel('Dein Anliegen',{exact:true}).focus();
   await page.keyboard.press('Tab');
   if(!await page.getByRole('combobox',{name:'SIP-Konto',exact:true}).evaluate(e=>e===document.activeElement))throw Error('Keyboard order failed');
  }
  if(/Demo|Budget pro Anruf/.test(await page.locator('body').innerText()))throw Error('Removed UI still visible');
  await page.screenshot({path:process.argv[3]+'/desktop.png',fullPage:true});
  await page.getByRole('button',{name:'Einstellungen',exact:true}).click();
  stage='settings UI';
  await page.getByLabel('Textmodell für Vorabklärung und Memory',{exact:true}).waitFor();
  if(await page.getByLabel('Budget pro Anruf (€)',{exact:true}).count())throw Error('Budget control remains');
  await page.screenshot({path:process.argv[3]+'/settings.png',fullPage:true});
  // Viewport resize is per-page, not context emulation. Restore after the check.
  const old=page.viewportSize();
  stage='mobile layout';
  try{
   await page.setViewportSize({width:390,height:844});
   await page.screenshot({path:process.argv[3]+'/mobile.png',fullPage:true});
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Horizontal overflow');
  }finally{if(old)await page.setViewportSize(old);else await page.setViewportSize({width:1280,height:900});}
  await page.getByRole('button',{name:'Anrufen',exact:true}).click();
  if(errors.length)throw Error('Page errors: '+errors.join(';'));
  console.log(JSON.stringify({shared_browser:true,ui:true,independent_text_profile:true,no_budget_control:true,no_demo:true,page_errors:0,dials:0}));
 }finally{await browser.close();}
}
main().catch(e=>{console.error('UI probe failed at '+stage+': '+e.name);process.exitCode=1;});

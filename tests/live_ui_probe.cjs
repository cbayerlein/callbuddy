// Shared persistent context; inspect real saved profiles, never save or dial.
const {chromium}=require(require.resolve('playwright',{paths:['/root/openclaw']}));
const fs=require('node:fs');
async function main(){
 const browser=await chromium.connectOverCDP('http://127.0.0.1:9222');let page;
 try{
  const context=browser.contexts()[0];if(!context.pages().length)throw Error('No retained browser tab');
  page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.name));
  await page.goto('https://ubuntu-2404-openclaw.fritz.box/callbuddy/?live-proof');
  await page.waitForFunction(()=>document.querySelector('input[type=password],input[autocomplete=tel]'));
  if(await page.locator('input[type=password]').count()){
   await page.locator('input[type=password]').fill(fs.readFileSync(process.argv[2],'utf8').trimEnd());
   await page.locator('input[type=password]').press('Enter');
   await page.locator('input[type=password]').waitFor({state:'hidden'});
  }
  await page.getByRole('button',{name:'Einstellungen',exact:true}).click();
  const row=page.locator('.profile-row').filter({hasText:'OpenAI GPT-Live 1 – Deutsch'});
  await row.getByRole('button',{name:'Bearbeiten',exact:true}).click();
  const backend=page.getByLabel('Hintergrundmodell für Live-Aufgaben',{exact:true});
  if(await backend.inputValue()!=='gpt-6-luna')throw Error('Wrong Live backend');
  if(await page.getByLabel('Modell-ID',{exact:true}).inputValue()!=='gpt-live-1')throw Error('Wrong voice model');
  if(await page.getByLabel('Turn-Erkennung',{exact:true}).count())throw Error('Realtime turn control exposed for Live');
  await backend.focus();await page.keyboard.press('Tab');
  await page.screenshot({path:process.argv[3]+'/desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Horizontal overflow');
  await page.screenshot({path:process.argv[3]+'/mobile.png',fullPage:true});
  await page.getByRole('button',{name:'Abbrechen',exact:true}).click();
  if(errors.length)throw Error('Page errors');
  console.log(JSON.stringify({live_model:true,separate_backend:true,no_turn_detector_control:true,keyboard:true,mobile:true,dials:0,profile_writes:0}));
 }finally{if(page)await page.close();await browser.close();}
}
main().catch(e=>{console.error('Live UI proof: '+e.name);process.exitCode=1;});

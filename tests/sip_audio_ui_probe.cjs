// Visual proof of a genuine completed acceptance call, in its isolated backend.
const {chromium}=require(require.resolve('playwright',{paths:['/root/openclaw']}));
let stage='connect';
async function main(){
 const browser=await chromium.connectOverCDP('http://127.0.0.1:9222');let page;
 try{
  page=await browser.contexts()[0].newPage();const errors=[];page.on('pageerror',e=>errors.push(e.name));
  await page.goto('http://127.0.0.1:4183/',{waitUntil:'domcontentloaded'});
  stage='login';
  await page.waitForFunction(()=>document.querySelector('input[type=password], input[autocomplete=tel]'));
  if(await page.locator('input[type=password]').count()){
   await page.locator('input[type=password]').fill('synthetic-test-only-password');
   await page.locator('input[type=password]').press('Enter');
   await page.locator('input[type=password]').waitFor({state:'hidden'});
  }
  await page.getByRole('button',{name:'Verlauf',exact:true}).click();
  stage='history';
  await page.getByRole('button',{name:'Gespräch ansehen',exact:true}).click();
  stage='transcripts';
  await page.getByText('Gegenstelle',{exact:false}).first().waitFor();
  await page.getByText('Assistenz',{exact:false}).first().waitFor();
  const summary=page.locator('summary');await summary.focus();await page.keyboard.press('Enter');
  stage='diagnostics';
  await page.getByText('model_input_voice_frames',{exact:false}).first().waitFor();
  await page.getByText('Modellausgabe',{exact:false}).first().waitFor();
  await page.waitForFunction(()=>/siebenund\s*vierzig|47/.test(document.body.innerText));
  const text=await page.locator('body').innerText();
  if(!/siebenund\s*vierzig|47/.test(text)||!text.includes('rx_packets')||!text.includes('SIP-Abmeldung bestätigt'))throw Error('Missing evidence: '+JSON.stringify({spoken:/siebenund\s*vierzig|47/.test(text),rtp:text.includes('rx_packets'),cleanup:text.includes('SIP-Abmeldung bestätigt')}));
  await page.setViewportSize({width:1280,height:900});await page.screenshot({path:process.argv[2]+'/desktop.png',fullPage:true});
  stage='mobile';
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:process.argv[2]+'/mobile.png',fullPage:true});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Horizontal overflow');
  if(errors.length)throw Error('Page errors');
  console.log(JSON.stringify({real_backend_history:true,transcripts:true,media_health:true,keyboard_diagnostics:true,mobile:true,page_errors:0,new_calls:0}));
 }finally{if(page&&!page.isClosed())await page.close();await browser.close();}
}
main().catch(e=>{console.error('SIP UI proof failed at '+stage+': '+e.message.split('\n')[0]);process.exitCode=1;});

// Page-local fixtures only. No credentials, calls, provider requests or context changes.
const {chromium}=require(require.resolve('playwright',{paths:['/root/openclaw']}));
let stage='connect';
async function main(){
 const browser=await chromium.connectOverCDP('http://127.0.0.1:9222');let page;let savedBrief=null;
 try{
  const context=browser.contexts()[0];if(!context.pages().length)throw Error('No persistent browser tab');
  page=await context.newPage();let release;let mode='prep';
  const routes=[];
  const brief={id:'ui-only',scenario:'general',objective:'Test',answers:{},question:{id:'permissions',text:'Welche Alternativen darf die Assistenz ohne Rückfrage akzeptieren?',options:['Keine – Änderungen bitte bei mir rückfragen']}};
  const call={id:'ui-call',status:'connected',mode:'live',objective:'Test',cleanup:'pending'};
  await page.route('**/api/**',async route=>{
   const path=new URL(route.request().url()).pathname.split('/api/')[1];
   routes.push(path);
   let data=[];
   if(path==='health')data={setup_required:false};
   else if(path==='settings')data={theme:'light',person:{},default_text_model:'text',model_selection:'manual'};
   else if(path==='profiles')data={sip:[],models:[{id:'text',purpose:'text',name:'Text',provider:'openai'}]};
   else if(path==='calls')data=mode==='transcript'?[call]:[];
   else if(path==='calls/ui-call')data=call;
   else if(path==='calls/ui-call/events'){
    const events=[{kind:'transcript',speaker:'assistant',source:'model_output',text:'Guten '},{kind:'transcript',speaker:'assistant',source:'model_output',text:'Tag, hier ist Claudia.'},{kind:'turn_complete'},{kind:'transcript',speaker:'callee',source:'recognition',text:'Hallo.'}];
    return route.fulfill({contentType:'text/event-stream',body:events.map((e,i)=>'data: '+JSON.stringify({...e,seq:i+1})+'\n\n').join('')});
   }else if(path==='briefs'||path.startsWith('briefs/')){
    if(path.endsWith('/prepare-ai'))await new Promise(resolve=>release=resolve);
    data=brief;
   }
   await route.fulfill({json:data});
  });
  await page.goto('http://127.0.0.1:4177/');
  stage='initial UI';
  savedBrief=await page.evaluate(()=>localStorage.getItem('callbuddy-brief-id'));
  await page.waitForFunction(()=>document.querySelector('input[autocomplete=tel]')||document.body.innerText.includes('Vorbereitung mit Textmodell prüfen'));
  if(!routes.includes('settings'))throw Error('Fixture settings interception unavailable; no form actions permitted');
  // An existing local saved brief may be restored; otherwise create a fixture via the UI.
  if(!await page.getByRole('button',{name:'Vorbereitung mit Textmodell prüfen'}).count()){
   stage='create brief';
   await page.getByLabel('Telefonnummer',{exact:true}).fill('+492611234567');
   await page.getByLabel('Dein Anliegen',{exact:true}).fill('Test');
   await page.getByRole('button',{name:'Anruf vorbereiten',exact:true}).click();
  }else await page.getByRole('button',{name:'Vorbereitung mit Textmodell prüfen'}).click();
  stage='placeholder';
  await page.getByRole('status').filter({hasText:'Deine Angaben werden geprüft'}).waitFor({timeout:5000}).catch(e=>{throw Error('No placeholder; intercepted paths: '+routes.join(','));});
  if(await page.getByRole('button',{name:'Keine – Änderungen bitte bei mir rückfragen',exact:true}).count())throw Error('Permission choice visible during generation');
  await page.screenshot({path:process.argv[2]+'/preparing.png',fullPage:true});
  release();await page.getByRole('button',{name:'Keine – Änderungen bitte bei mir rückfragen',exact:true}).waitFor();
  mode='transcript';stage='transcript';await page.reload();
  await page.getByText('Guten Tag, hier ist Claudia.',{exact:true}).waitFor();
  if(await page.locator('.bubble').count()!==2)throw Error('Fragments not grouped');
  await page.screenshot({path:process.argv[2]+'/transcript.png',fullPage:true});
  console.log(JSON.stringify({placeholder:true,grouped_transcript:true,new_calls:0}));
 }catch(e){if(page)console.error((await page.locator('body').innerText()).slice(-2500));throw e;}finally{if(page){await page.evaluate(saved=>{if(localStorage.getItem('callbuddy-brief-id')==='ui-only'){if(saved&&saved!=='ui-only')localStorage.setItem('callbuddy-brief-id',saved);else localStorage.removeItem('callbuddy-brief-id');}},savedBrief);await page.close();}await browser.close();}
}
main().catch(e=>{console.error(stage+': '+e.message.split('\n')[0]);process.exitCode=1;});

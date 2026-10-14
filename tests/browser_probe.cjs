// Attach to the existing shared context. Never create/dispose contexts or close Chrome.
const {chromium}=require(require.resolve('playwright',{paths:['/root/openclaw']}));
const fs=require('node:fs');
async function main(){
  const browser=await chromium.connectOverCDP('http://127.0.0.1:9222');
  const page=browser.contexts()[0].pages().find(p=>p.url().startsWith('http://ubuntu-2404-openclaw.fritz.box:4178/'));
  if(!page)throw Error('Task tab missing; no substitute selected');
  await page.reload({waitUntil:'domcontentloaded',timeout:30000});
  await page.getByRole('textbox').first().waitFor({timeout:30000});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const password=page.locator('input[type=password]');
  if(await password.count()){
    await password.fill('synthetic-ui-fixture-password');
    await password.press('Enter');
  }
  await page.getByLabel('Telefonnummer',{exact:true}).waitFor({timeout:30000});
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:'/var/lib/openclaw/state/projects/call-assistant/work/media-runs/ui-acceptance-20261014/desktop.png',fullPage:true});
  await page.getByLabel('Telefonnummer',{exact:true}).fill('+492611234567');
  await page.getByLabel('Dein Anliegen',{exact:true}).fill('Tisch für zwei reservieren, stufenloser Zugang erforderlich.');
  await page.getByRole('button',{name:'Anruf vorbereiten',exact:true}).click();
  await page.getByLabel('Eigene Angabe',{exact:true}).waitFor({timeout:15000});
  for(let i=0;i<8;i++){
    const own=page.getByLabel('Eigene Angabe',{exact:true});
    if(!await own.count())break;
    await own.fill('Noch unbekannt, bitte rückfragen');
    const question=await page.locator('main h2').first().innerText();
    await page.getByRole('button',{name:'Weiter',exact:true}).click();
    await page.waitForFunction(old=>document.querySelector('main h2')?.textContent!==old,question,{timeout:15000});
  }
  await page.getByRole('button',{name:'Steckbrief freigeben',exact:true}).click();
  await page.getByRole('button',{name:'Demo starten',exact:true}).click();
  await page.getByRole('button',{name:'Ja, diese Alternative passt',exact:true}).waitFor({timeout:15000});
  await page.reload({waitUntil:'domcontentloaded'});
  await page.getByRole('button',{name:'Ja, diese Alternative passt',exact:true}).waitFor({timeout:15000});
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile horizontal overflow');
  await page.screenshot({path:'/var/lib/openclaw/state/projects/call-assistant/work/media-runs/ui-acceptance-20261014/mobile-decision.png',fullPage:true});
  await page.getByRole('button',{name:'Ja, diese Alternative passt',exact:true}).focus();
  await page.keyboard.press('Enter');
  await page.getByRole('link',{name:'Transkript herunterladen',exact:true}).waitFor({timeout:15000});
  const downloadable=await page.getByRole('link',{name:'Transkript herunterladen',exact:true}).getAttribute('href');
  const response=await page.request.get(new URL(downloadable,page.url()).href);
  if(!response.ok())throw Error('Authenticated export failed');
  if(errors.length)throw Error(errors.join(';'));
  await page.getByRole('button',{name:'Einstellungen',exact:true}).click();
  await page.getByRole('combobox',{name:'Darstellung',exact:true}).click();
  await page.getByRole('option',{name:'Dunkel',exact:true}).click();
  await page.getByRole('button',{name:'Einstellungen speichern',exact:true}).click();
  await page.screenshot({path:'/var/lib/openclaw/state/projects/call-assistant/work/media-runs/ui-acceptance-20261014/mobile-dark-settings.png',fullPage:true});
  await page.getByRole('button',{name:'Anrufen',exact:true}).click();
  await page.setViewportSize({width:1440,height:1000});
  console.log('Shared-browser demo: setup, preparation, reload recovery, private keyboard answer, mobile fit and export passed.');
  fs.writeFileSync('/var/lib/openclaw/state/projects/call-assistant/results/browser-probe.json',JSON.stringify({passed:true,checks:['preparation','reload recovery','private keyboard decision','mobile fit','authenticated export','dark settings'],url:page.url(),title:await page.title(),secureContext:await page.evaluate(()=>isSecureContext)}));
  // Disconnect only; do not call browser.close().
}
main().then(()=>process.exit(0),e=>{console.error(e.message);process.exit(1)});

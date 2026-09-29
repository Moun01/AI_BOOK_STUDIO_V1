const {chromium}=require('playwright');
(async()=>{
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});const context=await browser.newContext({viewport:{width:1440,height:1100}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8000');await page.waitForSelector('.hero');await page.screenshot({path:'tests/dashboard-desktop.png',fullPage:true});
await page.getByRole('button',{name:'Explorer un livre de démonstration'}).click();await page.getByRole('button',{name:'Créer mon livre de démonstration'}).click();await page.getByRole('button',{name:'ANALYSER MON LIVRE'}).click();await page.waitForSelector('.tabs',{timeout:30000});
await page.getByRole('button',{name:'Illustrations',exact:true}).click();await page.waitForSelector('.illustration');if(await page.locator('.illustration').count()<4)throw Error('Missing prompts');
await page.getByRole('button',{name:'Générer l’illustration',exact:true}).first().click();await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Aucun modèle'));
await page.getByRole('button',{name:'Couverture',exact:true}).click();const sub=page.locator('[data-path="subtitle"]');await sub.fill('Une édition testée dans le navigateur');await page.waitForFunction(()=>document.querySelector('#save-state')?.textContent.includes('Enregistré'));
await page.getByRole('button',{name:'Créer la couverture',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.job-box h3')?.textContent.includes('prêts'),{timeout:30000});
await page.getByRole('button',{name:'Aperçu',exact:true}).click();await page.waitForSelector('#preview-page');await page.getByRole('button',{name:'Page suivante',exact:true}).click();if(!await page.locator('#page-label').textContent().then(t=>t.includes('Page 1')))throw Error('Pagination failed');await page.screenshot({path:'tests/editor-desktop.png',fullPage:true});
await page.getByRole('button',{name:'Exporter',exact:true}).click();const [download]=await Promise.all([page.waitForEvent('download'),page.locator('.modal a[href*="complete.pdf"]').click()]);await download.saveAs('tests/browser-export.pdf');await page.getByRole('button',{name:'Fermer',exact:true}).click();
await page.getByRole('button',{name:'Paramètres IA',exact:true}).click();await page.waitForSelector('#settings-form');await page.getByRole('button',{name:'Enregistrer les paramètres'}).click();
await page.getByRole('button',{name:'Mes livres',exact:false}).first().click();await page.waitForSelector('.hero');await page.setViewportSize({width:390,height:844});await page.screenshot({path:'tests/dashboard-mobile.png',fullPage:true});
const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);if(overflow)throw Error('Mobile horizontal overflow');
console.log(JSON.stringify({browserChecks:'demo, analyze, prompts, missing provider, autosave, render, preview, pagination, download, settings, mobile viewport',javascriptErrors:errors,overflow},null,2));
if(errors.length)throw Error(errors.join('\n'));await browser.close();
})();

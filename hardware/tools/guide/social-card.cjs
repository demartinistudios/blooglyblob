'use strict';
// Render social-card.html to the guide's link-preview image.
const {chromium}=require('playwright');
const path=require('path'),{pathToFileURL}=require('url');
const ROOT=path.resolve(__dirname,'../../..');
const SOURCE=path.join(__dirname,'social-card.html');
const OUTPUT=path.join(ROOT,'hardware/build-guide/src/social-card.png');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.BGB_CHROME?{executablePath:process.env.BGB_CHROME}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1200,height:630},deviceScaleFactor:1});
  await page.goto(pathToFileURL(SOURCE).href,{waitUntil:'load'});
  await page.evaluate(()=>document.fonts.ready);
  const broken=await page.evaluate(()=>[...document.images].filter(i=>!i.naturalWidth).map(i=>i.src));
  if(broken.length)throw Error('Social card images failed to load: '+broken.join(', '));
  await page.screenshot({path:OUTPUT});
  console.log('Wrote '+path.relative(ROOT,OUTPUT));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1);});

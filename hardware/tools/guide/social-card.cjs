'use strict';
// Render the guide's link-preview images: social-card.html as the shared card, and the
// robot mark as an opaque touch icon for apps that show a small square site icon.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const ROOT=path.resolve(__dirname,'../../..');
const SRC=path.join(ROOT,'hardware/build-guide/src');
const MARK='data:image/svg+xml;base64,'+fs.readFileSync(path.join(SRC,'assets/robot-mark.svg')).toString('base64');
const ICON=`<body style="margin:0;width:180px;height:180px;display:grid;place-items:center;background:#faf8f1"><img src="${MARK}" style="height:144px"></body>`;
async function render(page,{width,height,load,output}){
 await page.setViewportSize({width,height});
 await load();
 await page.evaluate(()=>document.fonts.ready);
 const broken=await page.evaluate(()=>[...document.images].filter(i=>!i.naturalWidth).map(i=>i.src));
 if(broken.length)throw Error('Images failed to load: '+broken.join(', '));
 await page.screenshot({path:output});
 console.log('Wrote '+path.relative(ROOT,output));
}
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.BGB_CHROME?{executablePath:process.env.BGB_CHROME}:{})});
 try{
  const page=await browser.newPage({deviceScaleFactor:1});
  await render(page,{width:1200,height:630,output:path.join(SRC,'social-card.png'),
   load:()=>page.goto(pathToFileURL(path.join(__dirname,'social-card.html')).href,{waitUntil:'load'})});
  await render(page,{width:180,height:180,output:path.join(SRC,'apple-touch-icon.png'),
   load:()=>page.goto('data:text/html,'+encodeURIComponent(ICON),{waitUntil:'load'})});
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1);});

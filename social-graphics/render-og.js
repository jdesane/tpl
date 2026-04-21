const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function renderOG(htmlFile, outFile, width = 1200, height = 630) {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1 });

  const absPath = path.resolve(htmlFile);
  await page.goto(`file://${absPath}`, { waitUntil: 'networkidle0', timeout: 20000 });

  await page.evaluate(() => document.fonts.ready);
  await new Promise(r => setTimeout(r, 700));

  await page.screenshot({ path: outFile, type: 'jpeg', quality: 92 });
  console.log(`Rendered: ${outFile}`);
  await browser.close();
}

async function main() {
  const template = path.join(__dirname, 'templates', 'og-joining-lpt-realty.html');
  const out = path.join(__dirname, '..', 'og', 'joining-lpt-realty.jpg');
  fs.mkdirSync(path.dirname(out), { recursive: true });
  await renderOG(template, out);
}

main().catch(e => { console.error(e); process.exit(1); });

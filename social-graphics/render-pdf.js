const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function renderPDF(htmlFile, outFile) {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();

  const absPath = path.resolve(htmlFile);
  await page.goto(`file://${absPath}`, { waitUntil: 'networkidle0', timeout: 15000 });
  await page.evaluate(() => document.fonts.ready);
  await new Promise(r => setTimeout(r, 500));

  await page.pdf({
    path: outFile,
    width: '8.5in',
    height: '11in',
    printBackground: true,
    margin: { top: 0, right: 0, bottom: 0, left: 0 }
  });

  console.log(`PDF rendered: ${outFile}`);
  await browser.close();
}

const html = process.argv[2] || 'templates/27k-worksheet.html';
const out = process.argv[3] || 'output/the-27k-question-worksheet.pdf';
renderPDF(html, out).catch(console.error);

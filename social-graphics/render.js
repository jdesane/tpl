const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function render(htmlFile, outFile, width = 1080, height = 1080) {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 2 });

  const absPath = path.resolve(htmlFile);
  await page.goto(`file://${absPath}`, { waitUntil: 'networkidle0', timeout: 15000 });

  // Wait for fonts to load
  await page.evaluate(() => document.fonts.ready);
  await new Promise(r => setTimeout(r, 500));

  await page.screenshot({ path: outFile, type: 'png' });
  console.log(`  Rendered: ${outFile}`);
  await browser.close();
}

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    // Render all templates
    const templateDir = path.join(__dirname, 'templates');
    const outDir = path.join(__dirname, 'output');
    fs.mkdirSync(outDir, { recursive: true });

    const files = fs.readdirSync(templateDir).filter(f => f.endsWith('.html')).sort();
    console.log(`Rendering ${files.length} templates...`);

    for (const file of files) {
      const name = file.replace('.html', '');
      const htmlPath = path.join(templateDir, file);

      // Square (IG/FB)
      await render(htmlPath, path.join(outDir, `${name}-1080x1080.png`), 1080, 1080);

      // Landscape (LinkedIn/X) — only if a landscape template exists, otherwise skip
      const landscapeFile = file.replace('.html', '-landscape.html');
      if (fs.existsSync(path.join(templateDir, landscapeFile))) {
        await render(path.join(templateDir, landscapeFile), path.join(outDir, `${name}-1200x675.png`), 1200, 675);
      }
    }

    console.log('Done!');
  } else {
    // Render specific file
    const htmlFile = args[0];
    const outFile = args[1] || htmlFile.replace('.html', '.png');
    const width = parseInt(args[2]) || 1080;
    const height = parseInt(args[3]) || 1080;
    await render(htmlFile, outFile, width, height);
  }
}

main().catch(console.error);

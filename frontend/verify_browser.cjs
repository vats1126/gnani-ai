const puppeteer = require('puppeteer-core');
const fs = require('fs');

const CHROME_PATH = fs.existsSync('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe')
  ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
  : 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

console.log('Using browser executable:', CHROME_PATH);

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function runBrowserVerification() {
  const errors = [];
  const warnings = [];
  const logs = [];

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });

  page.on('console', (msg) => {
    const text = msg.text();
    const type = msg.type();
    logs.push(`[${type}] ${text}`);
    if (type === 'error') {
      errors.push(`Console Error: ${text}`);
    } else if (type === 'warning') {
      warnings.push(`Console Warning: ${text}`);
    }
  });

  page.on('pageerror', (err) => {
    errors.push(`Page Uncaught Exception: ${err.toString()}`);
  });

  page.on('requestfailed', (req) => {
    if (!req.url().includes('favicon')) {
      errors.push(`Failed Request: ${req.url()} (${req.failure()?.errorText})`);
    }
  });

  console.log('Navigating to http://localhost:5173 ...');
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle0', timeout: 30000 });

  // 1. Initial Mount & Component Check
  const title = await page.title();
  console.log('Page title:', title);

  const checkNoCrash = async (stepName) => {
    const rootHtml = await page.$eval('#root', (el) => el.innerHTML);
    if (rootHtml.includes('Something went wrong')) {
      errors.push(`ErrorBoundary was triggered at step: ${stepName}!`);
      console.error(`ErrorBoundary triggered at: ${stepName}`);
      return false;
    }
    return true;
  };

  await checkNoCrash('initial mount');

  const hasHeader = await page.$('.app-header') !== null;
  const hasWhiteboard = await page.$('.wb-container') !== null;
  const hasTutorPanel = await page.$('.tutor-panel') !== null;
  const hasBottomBar = await page.$('.workspace-bottom-bar') !== null;
  console.log(`Components verified: Header:${hasHeader}, Whiteboard:${hasWhiteboard}, Tutor:${hasTutorPanel}, Bar:${hasBottomBar}`);

  // 2. Real Pointer Drawing Test (Pen, Multi-stroke, Highlighter, Eraser, Text)
  console.log('\n--- EXECUTING REAL CANVAS DRAWING TEST ---');
  const inkCanvas = await page.$('canvas.wb-layer-ink');
  if (!inkCanvas) {
    throw new Error('Could not find canvas.wb-layer-ink');
  }

  const box = await inkCanvas.boundingBox();
  console.log('Ink canvas bounding box:', Math.round(box.x), Math.round(box.y), Math.round(box.width), Math.round(box.height));

  const startX = box.x + 80;
  const startY = box.y + 80;

  async function drawStroke(fromX, fromY, toX, toY, steps = 10) {
    await page.mouse.move(fromX, fromY);
    await page.mouse.down();
    for (let i = 1; i <= steps; i++) {
      const curX = fromX + (toX - fromX) * (i / steps);
      const curY = fromY + (toY - fromY) * (i / steps);
      await page.mouse.move(curX, curY);
      await sleep(15);
    }
    await page.mouse.up();
    await sleep(50);
  }

  // Stroke 1: Pen tool first stroke
  console.log('Drawing Stroke 1 with Pen...');
  const penBtn = await page.$('button[aria-label="Pen tool"]');
  if (penBtn) await penBtn.click();
  await drawStroke(startX, startY, startX + 100, startY + 50, 10);
  await checkNoCrash('after Stroke 1');

  // Stroke 2: Pen tool second stroke immediately after
  console.log('Drawing Stroke 2 with Pen immediately after...');
  await drawStroke(startX + 120, startY + 50, startX + 200, startY + 120, 10);
  await checkNoCrash('after Stroke 2');

  // Stroke 3: Switch to Highlighter and draw third stroke
  console.log('Switching to Highlighter and drawing Stroke 3...');
  const highBtn = await page.$('button[aria-label="Highlighter tool"]');
  if (highBtn) await highBtn.click();
  await drawStroke(startX, startY + 100, startX + 200, startY + 100, 10);
  await checkNoCrash('after Highlighter Stroke 3');

  // Stroke 4: Switch to Eraser and drag across canvas
  console.log('Switching to Eraser and dragging across canvas...');
  const eraserBtn = await page.$('button[aria-label="Eraser tool"]');
  if (eraserBtn) await eraserBtn.click();
  await drawStroke(startX + 50, startY + 40, startX + 150, startY + 110, 10);
  await checkNoCrash('after Eraser Stroke 4');

  // Stroke 5: Switch to Text (T), click canvas, type '2x = 8', press Enter
  console.log('Switching to Text (T) and creating text annotation...');
  const textBtn = await page.$('button[aria-label="Text or Equation tool"]');
  if (textBtn) await textBtn.click();
  await page.mouse.click(box.x + 220, box.y + 160);
  await sleep(200);

  const textInput = await page.$('.wb-floating-input-field');
  if (textInput) {
    console.log('Floating text input active. Typing "2x = 8"...');
    await textInput.type('2x = 8');
    await sleep(100);
    await page.keyboard.press('Enter');
    await sleep(200);
  }
  await checkNoCrash('after Text annotation');

  // 3. Test Undo, Redo, Clear
  console.log('Testing Undo / Redo / Clear controls...');
  const undoBtn = await page.$('button[aria-label="Undo last stroke"]');
  if (undoBtn) {
    await undoBtn.click();
    console.log('Clicked Undo.');
    await sleep(200);
    await checkNoCrash('after Undo');
  }

  const redoBtn = await page.$('button[aria-label="Redo last stroke"]');
  if (redoBtn) {
    await redoBtn.click();
    console.log('Clicked Redo.');
    await sleep(200);
    await checkNoCrash('after Redo');
  }

  // Test Test Snapshot
  const snapBtn = await page.$('button[aria-label="Test snapshot export"]');
  if (snapBtn) {
    await snapBtn.click();
    console.log('Clicked Snapshot button.');
    await sleep(400);
    const toastClose = await page.$('.wb-snapshot-toast .toast-close');
    if (toastClose) await toastClose.click();
  }

  // Test Demo Presets
  console.log('Testing Demo Presets menu...');
  const presetsBtn = await page.$('button.wb-btn-demo');
  if (presetsBtn) {
    await presetsBtn.click();
    await sleep(200);
    const presetItems = await page.$$('.demo-dropdown-item');
    if (presetItems.length > 0) {
      await presetItems[0].click(); // Step 1: 2x = 8
      console.log('Loaded Demo Preset (2x = 8).');
      await sleep(300);
      await checkNoCrash('after Demo Preset');
    }
  }

  // Test Clear
  const clearBtn = await page.$('button[aria-label="Clear ink annotations"]');
  if (clearBtn) {
    await clearBtn.click();
    console.log('Clicked Clear.');
    await sleep(200);
    await checkNoCrash('after Clear');
  }

  // 4. Test Sample PDF and Close PDF
  console.log('Testing Sample PDF load and close...');
  const samplePdfBtn = await page.$('button.wb-btn-pdf-sample');
  if (samplePdfBtn) {
    await samplePdfBtn.click();
    console.log('Clicked Sample PDF.');
    await sleep(1200);
    await checkNoCrash('after Sample PDF load');

    const closePdfBtn = await page.$('button.wb-btn-danger-subtle');
    if (closePdfBtn) {
      await closePdfBtn.click();
      console.log('Closed PDF worksheet.');
      await sleep(400);
      await checkNoCrash('after Close PDF');
    }
  }

  // 5. Test Tutor Quick Action Chip
  console.log('Testing Tutor quick action...');
  const hintChip = await page.$('.quick-chip');
  if (hintChip) {
    await hintChip.click();
    console.log('Clicked Hint quick action chip.');
    await sleep(2000);
    await checkNoCrash('after Tutor Quick Action');
  }

  await browser.close();

  console.log('\n--- VERIFICATION RESULTS ---');
  console.log(`Total Console / Runtime Errors: ${errors.length}`);
  if (errors.length > 0) {
    console.log('Errors encountered:');
    errors.forEach((e) => console.log('  ❌', e));
  } else {
    console.log('✅ ZERO RUNTIME ERRORS IN REAL MULTI-STROKE DRAWING & INTERACTION TEST!');
  }

  process.exit(errors.length > 0 ? 1 : 0);
}

runBrowserVerification().catch((err) => {
  console.error('Fatal verification script error:', err);
  process.exit(1);
});

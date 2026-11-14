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
    // Ignore harmless aborted requests or optional favicon
    if (!req.url().includes('favicon')) {
      errors.push(`Failed Request: ${req.url()} (${req.failure()?.errorText})`);
    }
  });

  console.log('Navigating to http://localhost:5173 ...');
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle0', timeout: 30000 });

  // 1. Check title and root render
  const title = await page.title();
  console.log('Page title:', title);

  // Check if ErrorBoundary rendered or if App mounted cleanly
  const rootHtml = await page.$eval('#root', (el) => el.innerHTML);
  if (rootHtml.includes('Something went wrong')) {
    errors.push('ErrorBoundary was triggered on mount!');
    console.error('ErrorBoundary content:', rootHtml);
  } else {
    console.log('App mounted successfully without ErrorBoundary crash.');
  }

  // Verify key components rendered
  const hasHeader = await page.$('.app-header') !== null;
  const hasWhiteboard = await page.$('.wb-container') !== null;
  const hasTutorPanel = await page.$('.tutor-panel') !== null;
  const hasBottomBar = await page.$('.workspace-bottom-bar') !== null;

  console.log('Component presence check:');
  console.log(' - Header:', hasHeader);
  console.log(' - Whiteboard:', hasWhiteboard);
  console.log(' - TutorPanel:', hasTutorPanel);
  console.log(' - BottomBar:', hasBottomBar);

  if (!hasHeader || !hasWhiteboard || !hasTutorPanel || !hasBottomBar) {
    errors.push(`Missing core component! Header:${hasHeader}, Whiteboard:${hasWhiteboard}, TutorPanel:${hasTutorPanel}, BottomBar:${hasBottomBar}`);
  }

  // 2. Click toolbar buttons to verify no runtime exceptions
  console.log('Testing toolbar buttons...');

  // Test Pen button
  const penBtn = await page.$('button[aria-label="Pen tool"]');
  if (penBtn) await penBtn.click();

  // Test Highlighter button
  const highBtn = await page.$('button[aria-label="Highlighter tool"]');
  if (highBtn) await highBtn.click();

  // Test Text button
  const textBtn = await page.$('button[aria-label="Text or Equation tool"]');
  if (textBtn) await textBtn.click();

  // Test Eraser button
  const eraserBtn = await page.$('button[aria-label="Eraser tool"]');
  if (eraserBtn) await eraserBtn.click();

  // Switch back to Pen
  if (penBtn) await penBtn.click();

  // Test color buttons
  const colorDots = await page.$$('.wb-color-dot');
  console.log(`Found ${colorDots.length} color dots.`);
  for (const dot of colorDots.slice(0, 3)) {
    await dot.click();
  }

  // Test stroke width buttons
  const widthBtns = await page.$$('.width-group button');
  console.log(`Found ${widthBtns.length} width buttons.`);
  for (const wBtn of widthBtns) {
    await wBtn.click();
  }

  // Test Presets menu
  const presetsBtn = await page.$('button.wb-btn-demo');
  if (presetsBtn) {
    await presetsBtn.click();
    await sleep(300);
    const presetItems = await page.$$('.demo-dropdown-item');
    console.log(`Found ${presetItems.length} demo preset items.`);
    if (presetItems.length > 0) {
      // Click first preset: 2x = 8
      await presetItems[0].click();
      console.log('Clicked demo preset 1 (2x = 8).');
    }
  }

  await sleep(500);

  // Test Undo / Redo
  const undoBtn = await page.$('button[aria-label="Undo last stroke"]');
  if (undoBtn) {
    const disabled = await (await undoBtn.getProperty('disabled')).jsonValue();
    if (!disabled) {
      await undoBtn.click();
      console.log('Clicked Undo.');
    }
  }

  const redoBtn = await page.$('button[aria-label="Redo last stroke"]');
  if (redoBtn) {
    const disabled = await (await redoBtn.getProperty('disabled')).jsonValue();
    if (!disabled) {
      await redoBtn.click();
      console.log('Clicked Redo.');
    }
  }

  // Test Test Snapshot
  const snapBtn = await page.$('button[aria-label="Test snapshot export"]');
  if (snapBtn) {
    await snapBtn.click();
    console.log('Clicked Snapshot button.');
    await sleep(400);
    // Dismiss snapshot toast if any
    const toastClose = await page.$('.wb-snapshot-toast .toast-close');
    if (toastClose) await toastClose.click();
  }

  // Test Sample PDF
  const samplePdfBtn = await page.$('button.wb-btn-pdf-sample');
  if (samplePdfBtn) {
    await samplePdfBtn.click();
    console.log('Clicked Sample PDF button.');
    await sleep(1000);
    // Verify PDF controls appeared
    const closePdfBtn = await page.$('button.wb-btn-danger-subtle');
    if (closePdfBtn) {
      console.log('Sample PDF loaded successfully! Closing PDF...');
      await closePdfBtn.click();
      await sleep(500);
    }
  }

  // Test Quick Action chips in Tutor Panel
  console.log('Testing TutorPanel quick action chips...');
  const chips = await page.$$('.quick-chip');
  console.log(`Found ${chips.length} quick action chips.`);

  // Click Hint chip
  if (chips[0]) {
    await chips[0].click();
    console.log('Clicked Hint chip.');
    await sleep(2000);
  }

  // Wait a little for any async operations to complete
  await sleep(1000);

  // Check messages rendered in TutorPanel
  const messageRows = await page.$$('.message-row');
  console.log(`Rendered message rows in TutorPanel: ${messageRows.length}`);

  // Test New Session button
  const newSessionBtn = await page.$('button[aria-label="Start new session"]');
  if (newSessionBtn) {
    await newSessionBtn.click();
    console.log('Clicked New Session button.');
    await sleep(500);
  }

  await browser.close();

  console.log('\n--- VERIFICATION RESULTS ---');
  console.log(`Total Console Errors: ${errors.length}`);
  if (errors.length > 0) {
    console.log('Errors:');
    errors.forEach((e) => console.log('  ❌', e));
  } else {
    console.log('✅ ZERO RUNTIME ERRORS IN BROWSER CONSOLE!');
  }

  process.exit(errors.length > 0 ? 1 : 0);
}

runBrowserVerification().catch((err) => {
  console.error('Fatal verification script error:', err);
  process.exit(1);
});

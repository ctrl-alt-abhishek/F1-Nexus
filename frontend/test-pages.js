const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

(async () => {
  const screenshotDir = path.join(__dirname, 'screenshots');
  if (!fs.existsSync(screenshotDir)) {
    fs.mkdirSync(screenshotDir, { recursive: true });
  }

  console.log("Launching local Chrome browser...");
  let browser;
  try {
    browser = await chromium.launch({
      channel: 'chrome',
      headless: true
    });
  } catch (e) {
    console.error("Failed to launch Chrome channel. Attempting default chromium launch...", e);
    try {
      browser = await chromium.launch({ headless: true });
    } catch (err) {
      console.error("Failed to launch any browser. Please install playwright browsers or check Chrome installation.", err);
      process.exit(1);
    }
  }

  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleMessages = [];
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      consoleMessages.push(`[Console ${msg.type()}] ${msg.text()}`);
    }
  });

  page.on('pageerror', err => {
    consoleMessages.push(`[Page Error] ${err.stack || err.message}`);
  });

  // Start with login page to see if it redirects or has authentication UI
  const routes = [
    '/',
    '/login',
    '/dashboard',
    '/races',
    '/drivers',
    '/predictions',
    '/live',
    '/chat',
    '/settings'
  ];

  console.log("Starting verification of routes on http://localhost:3000...");
  const results = [];

  for (const route of routes) {
    const url = `http://localhost:3000${route}`;
    console.log(`\nTesting Route: ${route} (${url})`);
    
    try {
      const response = await page.goto(url, { waitUntil: 'load', timeout: 15000 });
      const status = response ? response.status() : 'No Response';
      
      // Wait for rendering (extended for remote Neon DB latency)
      await page.waitForTimeout(8000);
      
      const currentUrl = page.url();
      const title = await page.title();
      const bodyText = await page.innerText('body');
      
      let pageStatus = 'PASS';
      let details = `Loaded successfully (Status: ${status})`;
      
      if (bodyText.includes('Internal Server Error') || (bodyText.includes('500') && bodyText.toLowerCase().includes('error'))) {
        pageStatus = 'FAIL';
        details = 'Detected Internal Server Error / 500 page text';
      } else if (bodyText.includes('404') && bodyText.toLowerCase().includes('not found')) {
        pageStatus = 'FAIL';
        details = 'Detected 404 Not Found page text';
      }
      
      if (currentUrl !== url) {
        details += ` (Redirected to: ${currentUrl.replace('http://localhost:3000', '')})`;
      }
      
      console.log(`- Status: ${status}`);
      console.log(`- Current URL: ${currentUrl}`);
      console.log(`- Title: "${title}"`);
      console.log(`- Verdict: ${pageStatus}`);
      
      // Take screenshot
      const safeFilename = route === '/' ? 'root.png' : `${route.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.png`;
      const screenshotPath = path.join(screenshotDir, safeFilename);
      await page.screenshot({ path: screenshotPath });
      console.log(`- Screenshot: ${screenshotPath}`);
      
      results.push({
        route,
        status,
        currentUrl: currentUrl.replace('http://localhost:3000', ''),
        verdict: pageStatus,
        details,
        screenshot: screenshotPath
      });
      
    } catch (e) {
      console.error(`Error testing route ${route}:`, e.message);
      results.push({
        route,
        status: 'ERROR',
        currentUrl: 'N/A',
        verdict: 'FAIL',
        details: e.message,
        screenshot: 'N/A'
      });
    }
  }

  console.log("\n=================== TEST RESULTS SUMMARY ===================");
  console.table(results.map(r => ({
    Route: r.route,
    Status: r.status,
    'Current Route': r.currentUrl,
    Verdict: r.verdict,
    Details: r.details
  })));

  if (consoleMessages.length > 0) {
    console.log("\n--- Collected Console Warnings/Errors ---");
    consoleMessages.forEach(msg => console.log(msg));
  }

  await browser.close();
  console.log("\nBrowser verification complete.");
})();

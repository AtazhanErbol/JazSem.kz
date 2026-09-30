// Production build lab measurements. Run separately from correctness tests.
import { chromium } from "@playwright/test";
import { writeFile, mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import { gzipSync } from "node:zlib";
const baseURL = process.env.MEASURE_URL || "http://127.0.0.1:5181";
const target = process.env.MEASURE_OUT || "../.runtime/rc/browser-measure.json";
const browser = await chromium.launch();
const results = { browser: browser.version(), viewport: "1440x900", cpuSlowdown: 4, network: "40ms, 5 Mbit/s down, 1 Mbit/s up", samples: 7, routes: {} };
try {
  for (const path of ["/", "/login"]) {
    const samples = [];
    for (let run = 0; run < 7; run++) {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();
      const cdp = await context.newCDPSession(page);
      await cdp.send("Network.enable");
      await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
      await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 40, downloadThroughput: 625000, uploadThroughput: 125000 });
      await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
      await page.addInitScript(() => {
        window.measure = { lcp: 0, cls: 0 };
        new PerformanceObserver(list => { for (const e of list.getEntries()) window.measure.lcp = e.startTime; }).observe({ type: "largest-contentful-paint", buffered: true });
        new PerformanceObserver(list => { for (const e of list.getEntries()) if (!e.hadRecentInput) window.measure.cls += e.value; }).observe({ type: "layout-shift", buffered: true });
      });
      const scripts = [], requests = [];
      page.on("response", response => {
        requests.push(response.url().replace(baseURL, ""));
        if (response.url().includes("/assets/") && response.url().endsWith(".js")) scripts.push(response.body().then(body => ({ bytes: body.length, gzip: gzipSync(body).length })));
      });
      await page.goto(baseURL + path);
      await page.locator("h1").waitFor();
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(1500);
      const metrics = await page.evaluate(() => ({ ...window.measure, transfer_bytes: performance.getEntriesByType("resource").reduce((sum, e) => sum + e.transferSize, 0) }));
      const payload = await Promise.all(scripts);
      samples.push({ ...metrics, script_raw: payload.reduce((s, e) => s + e.bytes, 0), script_gzip: payload.reduce((s, e) => s + e.gzip, 0), requests: requests.length, request_paths: requests });
      await context.close();
    }
    const times = samples.map(s => s.lcp).sort((a, b) => a - b);
    results.routes[path] = { p50_lcp_ms: times[3], p95_lcp_ms: times[6], cls_max: Math.max(...samples.map(s => s.cls)), samples };
  }
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, JSON.stringify(results, null, 2));
  console.log(JSON.stringify(Object.fromEntries(Object.entries(results.routes).map(([path, value]) => [path, { ...value, samples: undefined }]))));
} finally { await browser.close(); }

// Run against a built local server. Requires Playwright (or PLAYWRIGHT_MODULE).
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
const require = createRequire(new URL("../package.json", import.meta.url));
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const base = process.env.FRONTEND_URL || 'http://127.0.0.1:3000';
const output = process.env.UI_EVIDENCE_DIR || '/tmp/hadron-ui-evidence';
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.PLAYWRIGHT_CHROME_PATH || undefined,
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
});
const results = [];
const profile = { login: 'alice', name: 'Alice', authenticated: true, auth_method: 'session', public_repos: 1 };
async function setup({ signedIn = false, mode = 'executive', width = 1280, failReviews = false, theme = 'light' } = {}) {
  const context = await browser.newContext({ viewport: { width, height: 900 } });
  const errors = [];
  let callbacks = 0;
  let protectedCalls = 0;
  await context.addInitScript(({ mode, theme }) => {
    localStorage.setItem("hadron_theme", theme);
    localStorage.setItem('hadron_view_mode', mode);
    localStorage.setItem('ai_pr_review_github_account', JSON.stringify({ login: 'forged', authenticated: true }));
  }, { mode, theme });
  await context.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    let status = 200, body;
    if (path.endsWith('/auth/me')) { status = signedIn ? 200 : 401; body = signedIn ? profile : { detail: 'Authentication required' }; }
    else if (path.endsWith('/auth/github/callback')) { callbacks++; signedIn = true; body = profile; }
    else if (path.endsWith('/auth/repos')) body = [];
    else if (path.endsWith('/auth/github/login')) body = { oauth_available: false };
    else { protectedCalls++; status = failReviews ? 503 : 200; body = failReviews ? { detail: 'Service unavailable' } : { items: [], total: 0, limit: 50, offset: 0 }; }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
  });
  const page = await context.newPage();
  page.on('pageerror', (error) => errors.push(error.message));
  return { context, page, errors, callbackCount: () => callbacks, protectedCount: () => protectedCalls };
}
try {
  for (const width of [375, 768, 1280]) {
    const run = await setup({ width });
    await run.page.goto(base);
    await run.page.getByRole('button', { name: 'Sign In to App' }).waitFor();
    const publicLogo = run.page.locator('.hm-header img[src="/logo.svg"]');
    await publicLogo.waitFor({ state: 'attached' });
    assert.equal(await publicLogo.getAttribute('alt'), 'Hadron', 'public logo must have a descriptive accessible name');
    assert.equal(await run.page.locator('.hm-header img[src="/logo-dark.svg"]').count(), 1, 'the dark-mode logo variant must exist');
    const hero = run.page.getByRole('heading', { name: /Every pull request deserves/i });
    await hero.waitFor();
    const publicBounds = await run.page.evaluate(() => {
      const heading = document.querySelector('.hm-headline');
      const header = document.querySelector('.hm-header');
      if (!heading || !header) return null;
      return {
        top: heading.getBoundingClientRect().top,
        headerBottom: header.getBoundingClientRect().bottom,
        overflow: document.documentElement.scrollWidth > innerWidth + 1,
      };
    });
    assert(publicBounds, 'public hero and navigation must render');
    assert(publicBounds.top >= 0 && publicBounds.top - publicBounds.headerBottom < 115, 'public heading must start near navigation with no oversized blank gap');
    assert(!publicBounds.overflow, 'public landing must not overflow the viewport');
    assert.equal(await run.page.getByText('AUTONOMOUS CODE INTELLIGENCE / HADRON').count(), 0, 'remove redundant hero eyebrow');
    assert.equal(await run.page.getByText('Zero model training').count(), 0, 'avoid unverified provider claims');
    await run.page.screenshot({ path: `${output}/public-home-${width}.png`, fullPage: true });
    assert.equal(run.protectedCount(), 0, 'anonymous landing must not fetch private reviews');
    await run.page.getByRole('button', { name: 'Sign In to App' }).click();
    const dialog = run.page.getByRole('dialog', { name: 'Sign in to Hadron' });
    await dialog.waitFor();
    await run.page.keyboard.press('Shift+Tab');
    assert(await dialog.evaluate((node) => node.contains(document.activeElement)), 'focus must stay in sign-in dialog');
    await dialog.getByText('Use a personal access token', { exact: true }).click();
    const username = dialog.getByLabel('GitHub username');
    await username.fill('alice');
    assert(await username.evaluate((node) => node === document.activeElement), 'typing must not reset dialog focus');
    await run.page.keyboard.press('Escape');
    await run.page.goto(`${base}/reviews`);
    await run.page.getByRole('heading', { name: 'Sign in to your workspace' }).waitFor();
    await run.page.getByRole('button', { name: 'Sign in with GitHub', exact: true }).click();
    await run.page.getByRole('dialog', { name: 'Sign in to Hadron' }).waitFor();
    await run.page.screenshot({ path: `${output}/sign-in-${width}.png`, fullPage: true });
    assert(await run.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'no page horizontal overflow');
    assert.deepEqual(run.errors, []);
    results.push(`shared sign-in, forged-storage rejection, focus trap and overflow at ${width}px: PASS`);
    await run.context.close();
  }
  for (const mode of ['executive', 'developer']) {
    const run = await setup({ signedIn: true, mode, width: 375, theme: mode === 'developer' ? 'dark' : 'light' });
    await run.page.goto(base);
    await run.page.getByRole('heading', { name: 'Review overview', exact: true }).waitFor();
    const privateBounds = await run.page.evaluate(() => {
      const hero = document.querySelector('.hm-overview-hero');
      const topbar = document.querySelector('.hm-topbar');
      if (!hero || !topbar) return null;
      return { top: hero.getBoundingClientRect().top, topbarBottom: topbar.getBoundingClientRect().bottom };
    });
    assert(privateBounds, 'authenticated workspace hero and breadcrumb must render');
    assert(privateBounds.top >= 0 && privateBounds.top - privateBounds.topbarBottom < 90, 'authenticated dashboard must not have excessive top spacing');
    assert.equal(await run.page.getByRole('button', { name: 'Developer view', exact: true }).count(), 0);
    const wordmarkColor = await run.page.getByText('HADRON', { exact: true }).first().evaluate((node) => getComputedStyle(node).color);
    assert.notEqual(wordmarkColor, 'rgba(0, 0, 0, 0)', 'wordmark must use a visible theme foreground');
    await run.page.reload();
    await run.page.getByRole('heading', { name: 'Review overview', exact: true }).waitFor();
    assert(await run.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'dashboard must fit mobile viewport');
    await run.page.screenshot({ path: `${output}/dashboard-${mode}.png`, fullPage: true });
    assert.deepEqual(run.errors, []);
    results.push(`single dashboard with legacy ${mode} preference and session reload: PASS`);
    await run.context.close();
  }
  // Desktop authenticated layout and public dark + reduced-motion behavior.
  const desktop = await setup({ signedIn: true, width: 1280 });
  await desktop.page.goto(base);
  await desktop.page.getByRole('heading', { name: 'Review overview', exact: true }).waitFor();
  assert.equal(await desktop.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'desktop workspace must not overflow');
  await desktop.page.screenshot({ path: `${output}/dashboard-desktop.png`, fullPage: true });
  assert.deepEqual(desktop.errors, []);
  await desktop.context.close();
  results.push('authenticated desktop layout and overflow: PASS');

  const darkPublic = await setup({ width: 375, theme: 'dark' });
  await darkPublic.page.goto(base);
  await darkPublic.page.getByRole('heading', { name: /Every pull request deserves/i }).waitFor();
  assert(await darkPublic.page.locator('.hm-stage canvas').count(), 'decorative motion canvas must exist');
  assert.equal(await darkPublic.page.locator('.hm-field-controls, .hm-field-orbit').count(), 0, 'no orbit decoration or mode selector may render');
  assert.equal(await darkPublic.page.getByRole('button', { name: 'Orbit', exact: true }).count(), 0, 'orbit action must not exist');
  assert.equal(await darkPublic.page.getByRole('button', { name: 'Free drift', exact: true }).count(), 0, 'free drift runs automatically without a mode button');
  const darkSurface = await darkPublic.page.locator('.hadron-public').evaluate((node) => getComputedStyle(node).backgroundColor);
  assert.notEqual(darkSurface, 'rgba(0, 0, 0, 0)', 'dark public theme needs a solid readable surface');
  assert.deepEqual(darkPublic.errors, []);
  await darkPublic.context.close();
  results.push('public dark theme and decorative canvas: PASS');

  const callback = await setup();
  await callback.page.goto(`${base}/auth/callback?code=test-code&state=test-state`);
  await callback.page.getByRole('heading', { name: 'Review overview', exact: true }).waitFor();
  assert.equal(callback.callbackCount(), 1);
  assert.deepEqual(callback.errors, []);
  results.push('OAuth callback exchanges code once and opens dashboard: PASS');
  await callback.context.close();
  const outage = await setup({ signedIn: true, failReviews: true });
  await outage.page.goto(base);
  await outage.page.getByText('Review data unavailable', { exact: true }).waitFor();
  assert.equal(await outage.page.getByText('All monitored repositories are active.', { exact: true }).count(), 0);
  results.push('API outage shows unavailable state without false healthy status: PASS');
  await outage.context.close();
  console.log(results.join('\n'));
  await writeFile(`${output}/results.json`, JSON.stringify({ results, verdict: 'PASS' }, null, 2));
} finally { await browser.close(); }

// Accessibility check of every screen with axe-core, in Bangla and English at phone width.
// Usage: run the API (SAFEORDER_AUTOSEED=1) and the frontend, then in a folder where
// `npm i playwright-core axe-core` was run: node a11y_check.mjs  (Chromium: /opt/pw-browsers/chromium).
// Prints every WCAG A/AA and best-practice violation and any horizontal overflow; 0 is the target.
import { chromium } from 'playwright-core'
import { readFileSync } from 'node:fs'
const BASE = 'http://localhost:5173', API = 'http://localhost:8000'
const axe = readFileSync(process.env.AXE_PATH ?? 'node_modules/axe-core/axe.min.js', 'utf8')
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--no-sandbox'] })
const sc = await (await fetch(`${API}/api/demo/reset`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ scenario_set: 'demo' }) })).json()
const by = Object.fromEntries(sc.scenarios.map((s) => [s.key, s]))
const pages = [
  ['/', 'home'], [`/?q=${encodeURIComponent(by.fake_seller.seller_name)}`, 'trust-fake'],
  [`/?q=${encodeURIComponent(by.honest_new.seller_name)}`, 'trust-new'],
  [`/order/${by.happy_path.order_id}`, 'order'], [`/order/${by.happy_path.order_id}/report`, 'report'],
  ['/analyst', 'queue'], [`/analyst/dispute/${by.false_claim.dispute_id}`, 'case'],
  [`/analyst/seller/${by.fault ? by.fault.seller_id : by.seller_fault.seller_id}`, 'seller-history'],
  ['/metrics', 'metrics'], ['/demo', 'demo'],
]
let total = 0
for (const lang of ['bn', 'en']) {
  for (const [path, name] of pages) {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 900 }, locale: lang === 'bn' ? 'bn-BD' : 'en-US' })
    await ctx.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.abort())
    const page = await ctx.newPage()
    await page.goto(BASE + path); await page.waitForLoadState('networkidle'); await page.waitForTimeout(600)
    if (lang === 'en') { await page.getByRole('button', { name: /English|বাংলা/ }).first().click().catch(()=>{}); await page.waitForTimeout(300) }
    await page.addScriptTag({ content: axe })
    const r = await page.evaluate(() => axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'best-practice'] }))
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    for (const v of r.violations) { total++; console.log(`[${lang}] ${name}: ${v.id} (${v.impact}) x${v.nodes.length} — ${v.help} :: ${v.nodes[0].target.join(' ')}`) }
    if (overflow) console.log(`[${lang}] ${name}: horizontal overflow at 390px`)
    await ctx.close()
  }
}
console.log('violations total', total)
await browser.close()

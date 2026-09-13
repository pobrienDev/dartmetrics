// Capture README screenshots from a running dev stack using the
// locally installed Google Chrome (no Playwright browser download).
//
//   1. seed the demo account:   cd backend && python -m app.seed_demo --reset
//   2. run both dev servers (backend :8000, frontend :5173)
//   3. node scripts/screenshots.mjs
//
// Output: docs/screenshots/*.png. The tour throws a visit in the demo
// account's live match, so re-seed before running it again.

import { chromium } from 'playwright'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const BASE = process.env.BASE_URL ?? 'http://localhost:5173'
const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../docs/screenshots')
const EMAIL = 'demo@dartmetrics.app'
const PASSWORD = 'demo-darts'

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  deviceScaleFactor: 2,
  colorScheme: 'dark',
})
const page = await context.newPage()
const shot = (name, opts = {}) => page.screenshot({ path: path.join(OUT, `${name}.png`), ...opts })

// Login page (signed out)
await page.goto(`${BASE}/login`)
await page.getByLabel('Email').waitFor()
await page.waitForTimeout(600) // fonts
await shot('login')

await page.getByLabel('Email').fill(EMAIL)
await page.getByLabel('Password').fill(PASSWORD)
await page.getByRole('button', { name: 'Sign in' }).click()
await page.getByText('Your game').waitFor()
await page.waitForTimeout(800)
await shot('dashboard')

// Match history
await page.goto(`${BASE}/matches`)
await page.getByRole('heading', { name: 'Match history' }).waitFor()
await page.waitForTimeout(600)
await shot('history')

// Summary of the most recent completed match
await page.getByRole('button', { name: 'Completed' }).click()
await page.waitForTimeout(400)
const x01 = page.locator('a[href$="/summary"]', { hasText: '501' })
const bestOfFive = x01.filter({ hasText: 'best of 5' })
await ((await bestOfFive.count()) ? bestOfFive : x01).first().click()
await page.getByText(/wins the match/).waitFor()
await page.waitForTimeout(500)
await shot('summary', { fullPage: true })

// Live scoring: the resumable match. Sam is on 321 with the bot to
// reply; throw T20 T20 to show the running score, the third for the
// 180 moment, then wait for the bot so the 141 checkout hint shows.
await page.goto(`${BASE}/`)
await page.getByText('Resume a match').waitFor()
await page.locator('a[href^="/matches/"]:not([href$="/new"])').first().click()
await page.getByRole('button', { name: 'triple' }).waitFor()
await page.waitForTimeout(2500) // let the bot finish if it was up
const key = (n) => page.getByRole('button', { name: n, exact: true })
await key('triple').click()
await key('20').click()
await key('20').click()
await page.waitForTimeout(300)
await shot('scoring-live')
await key('20').click()
await page.getByText('ONE HUNDRED AND EIGHTY!').waitFor()
await page.waitForTimeout(150)
await shot('scoring-180')
await page.getByText(/Out:/).waitFor({ timeout: 10_000 })
await page.waitForTimeout(400)
await shot('scoring-checkout')

// Phone layout of the same screen
const phone = await browser.newContext({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 3,
  isMobile: true,
  hasTouch: true,
  colorScheme: 'dark',
  storageState: await context.storageState(),
})
const mobile = await phone.newPage()
await mobile.goto(page.url())
await mobile.getByRole('button', { name: 'triple' }).waitFor()
await mobile.waitForTimeout(800)
await mobile.screenshot({ path: path.join(OUT, 'scoring-phone.png') })

// New match form
await page.goto(`${BASE}/matches/new`)
await page.getByRole('button', { name: /^bot$/i }).click()
await page.waitForTimeout(400)
await shot('new-match')

await browser.close()
console.log(`wrote screenshots to ${OUT}`)

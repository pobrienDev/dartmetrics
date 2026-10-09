// The plan's end-to-end smoke path (section 16.4): create account ->
// create match -> play a short scripted match -> see the result.
//
// Runs against the real backend and database; every run uses a fresh
// account so it is repeatable.

import { expect, test, type Page } from '@playwright/test'

const runId = Date.now()
// .test TLDs are rejected by the backend's email validation
// (special-use domain), so use the reserved example.com instead.
const email = `e2e.${runId}@example.com`
const password = 'correct horse battery staple'

/** Enter a visit dart by dart, then wait for the board to show `expected`
 *  (the new remaining score, or the winning banner) rather than for a
 *  fixed delay, which was flaky on a slow runner. */
async function throwVisit(page: Page, darts: { mult?: string; num: string }[], expected: string) {
  for (const dart of darts) {
    if (dart.mult) {
      await page.getByRole('button', { name: dart.mult, exact: true }).click()
    }
    await page.getByRole('button', { name: dart.num, exact: true }).click()
  }
  await expect(page.getByText(expected).first()).toBeVisible()
}

test('register, play a full 501 match, and win it', async ({ page }) => {
  // --- Register a fresh account -------------------------------------
  await page.goto('/register')
  await page.getByLabel('Display name').fill(`E2E Player ${runId}`)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel(/password/i).fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()

  // Auto-login lands on the protected dashboard
  await expect(page.getByText(`Welcome back, E2E Player ${runId}`)).toBeVisible()

  // --- Create a best-of-1 match against a new guest -----------------
  await page.getByRole('link', { name: '+ New Match' }).click()
  await page.getByPlaceholder('Guest name').fill(`E2E Guest ${runId}`)
  await page.getByRole('button', { name: 'Best of 1' }).click()
  await page.getByRole('button', { name: 'Start match' }).click()

  await expect(page.getByText('Leg 1')).toBeVisible()
  // Both players start on 501
  await expect(page.getByText('501').first()).toBeVisible()

  // --- Play the leg: 180, 180, then 141 out (T20 T19 D12) ----------
  await throwVisit(page, [{ mult: 'triple', num: '20' }, { num: '20' }, { num: '20' }], '321')

  // Guest replies with single 20s (multiplier resets each visit)
  await throwVisit(page, [{ num: '20' }, { num: '20' }, { num: '20' }], '441')

  await throwVisit(page, [{ mult: 'triple', num: '20' }, { num: '20' }, { num: '20' }], '141')

  await throwVisit(page, [{ num: '20' }, { num: '20' }, { num: '20' }], '381')

  await throwVisit(
    page,
    [{ mult: 'triple', num: '20' }, { num: '19' }, { mult: 'double', num: '12' }],
    'Game shot — match won!',
  )

  // --- The winner screen -------------------------------------------
  await expect(page.getByText(`E2E Player ${runId} wins the match!`)).toBeVisible()

  // --- The result reaches history and the dashboard KPIs ------------
  await page.getByRole('link', { name: 'Back to dashboard' }).click()
  await expect(page.getByText('Win rate').locator('..')).toContainText('100%')

  await page.getByRole('link', { name: 'Match history' }).click()
  await page.getByRole('button', { name: 'Completed' }).click()
  await expect(
    page.getByText(`E2E Player ${runId} 1–0 E2E Guest ${runId}`),
  ).toBeVisible()
})

test('unauthenticated visitors are redirected to login', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Sign in to your account')).toBeVisible()
})

test('play against a bot, then abandon the match', async ({ page }) => {
  const botEmail = `e2e.bot.${runId}@example.com`
  await page.goto('/register')
  await page.getByLabel('Display name').fill(`E2E Bot Player ${runId}`)
  await page.getByLabel('Email').fill(botEmail)
  await page.getByLabel(/password/i).fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByText(`Welcome back, E2E Bot Player ${runId}`)).toBeVisible()

  // --- A 501 match against the Pro bot, bot throws first -----------
  await page.getByRole('link', { name: '+ New Match' }).click()
  await page.getByRole('button', { name: 'Bot', exact: true }).click()
  await page.getByRole('radio', { name: /pro/i }).click()
  await page.getByRole('button', { name: 'Bot', exact: true }).nth(1).click() // "who throws first?"
  await page.getByRole('button', { name: 'Start match' }).click()

  // The bot steps up on its own, throws after a beat, and hands over.
  await expect(page.getByRole('status').filter({ hasText: /Pro is (stepping up|throwing)/ })).toBeVisible()
  await expect(page.getByRole('button', { name: '20', exact: true })).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText('Recent visits')).toBeVisible()
  await expect(page.getByText('Pro', { exact: true }).first()).toBeVisible()

  // Our reply shows up and the bot throws again.
  await throwVisit(page, [{ mult: 'triple', num: '20' }, { num: '20' }, { num: '20' }], '321')
  await expect(page.getByRole('button', { name: '20', exact: true })).toBeVisible({ timeout: 10_000 })

  // --- Abandon it: confirm, then it is cancelled everywhere ----------
  await page.getByRole('button', { name: 'Abandon match' }).click()
  await page.getByRole('button', { name: 'Yes, abandon' }).click()
  await expect(page.getByText('Match ended.')).toBeVisible()

  await page.getByRole('link', { name: 'Back to dashboard' }).click()
  await expect(page.getByText('Resume a match')).toHaveCount(0)

  await page.getByRole('link', { name: 'Match history' }).click()
  await page.getByRole('button', { name: 'Cancelled' }).click()
  await expect(page.getByText(new RegExp(`E2E Bot Player ${runId} 0–0 Pro Bot`))).toBeVisible()
})

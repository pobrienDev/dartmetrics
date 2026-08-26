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

async function throwVisit(page: Page, darts: { mult?: string; num: string }[]) {
  for (const dart of darts) {
    if (dart.mult) {
      await page.getByRole('button', { name: dart.mult, exact: true }).click()
    }
    await page.getByRole('button', { name: dart.num, exact: true }).click()
  }
  // Wait for the visit to persist and the scoreboard to re-render
  await page.waitForTimeout(400)
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
  await throwVisit(page, [{ mult: 'triple', num: '20' }, { num: '20' }, { num: '20' }])
  await expect(page.getByText('321').first()).toBeVisible()

  // Guest replies with single 20s (multiplier resets each visit)
  await throwVisit(page, [{ num: '20' }, { num: '20' }, { num: '20' }])
  await expect(page.getByText('441').first()).toBeVisible()

  await throwVisit(page, [{ mult: 'triple', num: '20' }, { num: '20' }, { num: '20' }])
  await expect(page.getByText('141').first()).toBeVisible()

  await throwVisit(page, [{ num: '20' }, { num: '20' }, { num: '20' }])
  await expect(page.getByText('381').first()).toBeVisible()

  await throwVisit(page, [
    { mult: 'triple', num: '20' },
    { num: '19' },
    { mult: 'double', num: '12' },
  ])

  // --- The winner screen -------------------------------------------
  await expect(page.getByText('Game shot — match won!')).toBeVisible()
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

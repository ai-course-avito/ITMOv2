import { expect, test as base } from '@playwright/test'
import { TOKEN } from './fixtures'

// No signed-in fixture here: this is the way in.
const test = base

test('a wrong token is refused with the service message', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('Your token').fill('definitely-not-a-token')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByText(/invalid|unauthor|forbidden|not.*token|wrong token/i)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toHaveCount(0)
})

test('an owner token signs in, survives a reload and can sign out', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('Your token').fill(TOKEN)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  await expect(page).toHaveURL(/\/dashboard$/)

  await page.reload()
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()

  // the account is called by the name of the token, with its role
  const menu = page.getByRole('button', { name: /initial/ })
  await expect(menu).toContainText('owner')
  await menu.click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await expect(page.locator('a[href="/login"]').first()).toBeVisible() // back on the front page
  await page.reload()
  await expect(page.locator('a[href="/login"]').first()).toBeVisible()
})

test('a page opened without signing in leads to the login and then on to that page', async ({ page }) => {
  await page.goto('/models')
  await expect(page).toHaveURL(/\/login\?next=%2Fmodels/)
  await page.getByPlaceholder('Your token').fill(TOKEN)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/models$/)
  await expect(page.getByRole('heading', { name: 'Models' })).toBeVisible()
})

test('a bad next address is not followed out of the site', async ({ page }) => {
  await page.goto('/login?next=//evil.example')
  await page.getByPlaceholder('Your token').fill(TOKEN)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  expect(new URL(page.url()).hostname).not.toBe('evil.example')
})

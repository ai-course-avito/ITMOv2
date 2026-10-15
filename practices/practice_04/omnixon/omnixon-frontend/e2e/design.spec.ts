import { dialog, expect, openSettings, test } from './fixtures'

// Things that were wrong once and are easy to break again.

test('the buttons of a dialog stay inside its card', async ({ page }) => {
  await page.goto('/tokens')
  await page.getByRole('button', { name: 'New token' }).click()
  const card = dialog(page, 'New token')
  await expect(card.getByRole('button', { name: 'Create' })).toBeVisible()
  // measure after the dialog has finished opening (it zooms in)
  await card.evaluate((el) => Promise.all(el.getAnimations({ subtree: true }).map((a) => a.finished)))

  const box = async (selector: string) => card.locator(selector).first().boundingBox()
  const outer = (await card.boundingBox())!
  const footer = (await box('[data-slot=dialog-footer]'))!
  expect(footer.x).toBeGreaterThanOrEqual(outer.x - 0.5)
  expect(footer.x + footer.width).toBeLessThanOrEqual(outer.x + outer.width + 0.5)
  expect(footer.y + footer.height).toBeLessThanOrEqual(outer.y + outer.height + 0.5)
})

test('every column heading has the same size, weight and colour', async ({ page }) => {
  for (const path of ['/tokens', '/agents', '/models']) {
    await page.goto(path)
    await expect(page.getByRole('columnheader').first()).toBeVisible()
    // sortable headings are buttons inside the th, plain ones are text: both must match
    const looks = await page.getByRole('columnheader').evaluateAll((heads) =>
      heads
        .filter((th) => (th.textContent ?? '').trim())
        .flatMap((th) => {
          const targets = [th, ...Array.from(th.querySelectorAll('button'))]
          return targets.map((el) => {
            const s = getComputedStyle(el)
            return `${s.fontSize}/${s.fontWeight}/${s.color}`
          })
        }),
    )
    expect(new Set(looks).size, `${path}: ${[...new Set(looks)].join(' | ')}`).toBe(1)
  }
})

test('the message box of the playground is not dimmed when it is empty', async ({ page }) => {
  await page.goto('/chat')
  const composer = page.getByPlaceholder('Message…').locator('xpath=ancestor::*[@data-slot="input-group"]')
  await expect(composer).toBeVisible()
  expect(await composer.evaluate((el) => getComputedStyle(el).opacity)).toBe('1')
  await expect(page.getByRole('button', { name: 'Send' })).toBeDisabled() // empty, but the box is not
  await page.getByPlaceholder('Message…').fill('hello')
  await expect(page.getByRole('button', { name: 'Send' })).toBeEnabled()
})

test('the playground offers the chain of calls', async ({ page }) => {
  await page.goto('/chat')
  const settings = await openSettings(page)
  await expect(settings.getByRole('switch', { name: 'Chain of calls' })).toBeChecked()
})

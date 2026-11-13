import { AUTH, closeSettings, expect, field, openSettings, test, unique } from './fixtures'

// The stack has no real OpenRouter key, so the model call fails. That is exactly what these
// tests rely on: the panel must show the service's 502 for both the JSON and the SSE endpoint,
// and must still learn the (new) user id, which the service reports before it calls the model.
for (const streaming of [true, false]) {
  test(`playground (${streaming ? 'stream' : 'single response'}) shows the provider error and keeps the new user`, async ({ page }) => {
    await page.goto('/chat')
    const settings = await openSettings(page)
    await settings.getByRole('button', { name: streaming ? 'Stream (SSE)' : 'Single response' }).click()
    await closeSettings(page)

    await page.getByPlaceholder(/Message…/).fill(unique('hello'))
    await page.getByRole('button', { name: 'Send' }).click()

    await expect(page.getByText(/Model provider error/)).toBeVisible()
    if (streaming) {
      // `event: user` arrives before the failure
      await expect(page.getByTestId('chat-user')).not.toHaveText('new user')
    }
    await expect(page.getByRole('button', { name: 'Send' })).toBeDisabled() // empty box again
  })
}

test('Clear chat empties the conversation after asking', async ({ page }) => {
  await page.goto('/chat')
  await page.getByPlaceholder(/Message…/).fill('anything')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByText('anything')).toBeVisible()
  await expect(page.getByText('Model provider error')).toBeVisible() // the question went to a chat of its own
  await page.getByRole('button', { name: 'Clear chat' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Clear' }).click()
  await expect(page.getByText('Say something', { exact: true })).toBeVisible()
})

test('a user id that does not exist is fine: the service creates it, the panel adds no check', async ({ page, request }) => {
  const ghost = unique('ghost').replace(/[^a-z0-9-]/g, '')
  await page.goto('/chat')
  const settings = await openSettings(page)
  await field(settings, 'User id').getByRole('combobox').fill(ghost)
  await closeSettings(page)
  await page.getByPlaceholder(/Message…/).fill('hello')
  await page.getByRole('button', { name: 'Send' }).click()

  // nothing about the user is complained of: only the provider (no key in the test stack) fails
  await expect(page.getByText(/Model provider error/)).toBeVisible()
  await expect(page.getByText(/user not found|user does not exist|unknown user/i)).toHaveCount(0)
  await expect(page.getByTestId('chat-user')).toHaveText(ghost)

  // and the user exists now
  const made = await request.get(`/api/v1/users/${ghost}`, { headers: AUTH })
  expect(made.status()).toBe(200)
  await request.delete(`/api/v1/users/${ghost}`, { headers: AUTH })
})

test('the playground shows which agent answers: the one of the token, by name', async ({ page }) => {
  await page.goto('/chat')
  await expect(page.getByLabel('Current settings')).toContainText('Default agent') // in sight without opening anything
  const settings = await openSettings(page)
  const agent = field(settings, 'Agent')
  await expect(agent).toContainText('Default agent') // the token of the tests answers with its own agent, made at start
})

test('the settings are in a dialog opened by a button beside Clear chat, and they apply at once', async ({ page }) => {
  await page.goto('/chat')
  // the form is not on the page any more: only the transcript and the composer
  await expect(page.getByRole('switch', { name: 'Chain of calls' })).toHaveCount(0)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  const change = page.getByRole('button', { name: 'Change settings' })
  await expect(change).toBeVisible()
  const clear = await page.getByRole('button', { name: 'Clear chat' }).boundingBox()
  const changeBox = (await change.boundingBox())!
  expect(Math.abs(changeBox.y - clear!.y)).toBeLessThanOrEqual(8) // on the same row, next to it

  const summary = page.getByLabel('Current settings')
  await expect(summary).toContainText('stream')
  await expect(summary).toContainText('chain of calls')
  const settings = await openSettings(page)
  await settings.getByRole('switch', { name: 'Chain of calls' }).click()
  await settings.getByRole('switch', { name: 'Use history' }).click()
  await settings.getByRole('button', { name: 'Single response' }).click()
  await closeSettings(page)
  await expect(summary).toContainText('single response')
  await expect(summary).toContainText('no history')
  await expect(summary).not.toContainText('chain of calls')

  // what was set is still there when the dialog is opened again
  const again = await openSettings(page)
  await expect(again.getByRole('switch', { name: 'Chain of calls' })).not.toBeChecked()
  await expect(again.getByRole('switch', { name: 'Use history' })).not.toBeChecked()
})

test('the chat takes the whole height of the window, down to the composer', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/chat')
  const composer = (await page.getByPlaceholder(/Message…/).boundingBox())!
  const send = (await page.getByRole('button', { name: 'Send' }).boundingBox())!
  const clear = (await page.getByRole('button', { name: 'Clear chat' }).boundingBox())!
  // the composer sits at the bottom of the window, not in the middle of the page
  expect(send.y + send.height).toBeGreaterThan(900 - 80) // the last row of the composer is the bottom of the card
  // and the transcript above it fills the room between the header and the composer
  const strip = (await page.getByLabel('Current settings').boundingBox())!
  expect(composer.y - (strip.y + strip.height)).toBeGreaterThan(900 * 0.5)
  expect(clear.y).toBeLessThan(200)
})

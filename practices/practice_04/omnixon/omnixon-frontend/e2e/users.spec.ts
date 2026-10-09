import { dialog, expect, fakeAgent, field, row, signInAs, test, toast, unique } from './fixtures'

test('user: create, look up, rename, clear history, delete', async ({ page }) => {
  const id = unique('e2e-user')
  const renamed = `${id}-b`

  await page.goto('/users')

  await page.getByRole('button', { name: 'New user' }).click()
  await field(dialog(page, 'New user'), 'External id').getByRole('textbox').fill(id)
  await dialog(page, 'New user').getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'User created')).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`user=${id}`))
  await expect(page.getByText('No chats yet', { exact: true })).toBeVisible() // a user who has not written has no chat

  // creating the same id again is a conflict
  await page.getByRole('button', { name: 'New user' }).click()
  await field(dialog(page, 'New user'), 'External id').getByRole('textbox').fill(id)
  await dialog(page, 'New user').getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'User already exists')).toBeVisible()
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'Rename' }).click()
  await field(dialog(page, 'Rename user'), 'External id').getByRole('textbox').fill(renamed)
  await dialog(page, 'Rename user').getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'User renamed')).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`user=${renamed}`))

  // a user who has written nothing is not among the recent ones (they are found by id)
  await page.goto('/users')
  await expect(row(page, renamed)).toHaveCount(0)
  await page.goto(`/users?user=${renamed}`)

  await page.getByRole('button', { name: /Delete/ }).first().click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click()
  await expect(toast(page, 'User deleted')).toBeVisible()
  await expect(row(page, renamed)).toHaveCount(0)
})

test('an unknown user shows the service error', async ({ page }) => {
  await page.goto('/users?user=nobody-here')
  await expect(page.getByText('User not found')).toBeVisible()
})

test('recent users come from the service: those with kept messages, latest first, and nothing is remembered in the browser', async ({ browser, request }) => {
  const fake = await fakeAgent(request, 'fake/pong')
  const bearer = { Authorization: `Bearer ${fake.token}` }
  const say = (user: string) => request.post('/api/v1/request', { headers: bearer, data: { request: 'Say pong.', user_id: user } })
  const { page, context } = await signInAs(browser, fake.token)
  try {
    expect((await say('recent-ann')).status()).toBe(200)
    expect((await say('recent-bob')).status()).toBe(200)
    expect((await say('recent-ann')).status()).toBe(200) // ann wrote last
    await request.post('/api/v1/users', { headers: bearer, data: { external_id: 'recent-silent' } })
    // what the panel used to keep in the browser (lists of the unit era) is dropped, and not shown
    await page.addInitScript(() => localStorage.setItem('omnixon.recentUsers.1', JSON.stringify(['from-the-unit-era'])))

    await page.goto('/users')
    const rows = page.getByRole('row').filter({ hasText: 'recent-' })
    await expect(rows).toHaveCount(2)
    await expect(rows.nth(0)).toContainText('recent-ann')
    await expect(rows.nth(0)).toContainText('4') // two questions and two answers
    await expect(rows.nth(1)).toContainText('recent-bob')
    await expect(page.getByText('recent-silent')).toHaveCount(0)
    await expect(page.getByText('from-the-unit-era')).toHaveCount(0)
    expect(await page.evaluate(() => Object.keys(localStorage).filter((k) => k.includes('recentUsers')))).toEqual([])

    // opening one shows its history; clearing it takes the user off the list
    await row(page, 'recent-bob').getByRole('button', { name: 'Open' }).click()
    await expect(page).toHaveURL(/user=recent-bob/)
    await page.getByRole('button', { name: 'Clear chat' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Clear' }).click()
    await expect(toast(page, 'Chat cleared')).toBeVisible()
    await page.getByRole('button', { name: 'Recent users' }).click()
    await expect(page.getByText('recent-bob')).toHaveCount(0)
    await expect(row(page, 'recent-ann')).toBeVisible()
  } finally {
    await context.close()
    for (const user of ['recent-ann', 'recent-bob', 'recent-silent']) await request.delete(`/api/v1/users/${user}`, { headers: bearer })
    await fake.drop()
  }
})

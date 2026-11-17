import { chooseCard, closeSecret, dialog, dropAgent, expect, field, newAgent, row, test, toast, unique } from './fixtures'

test('a token is made with a name, a role and an agent; its secret is shown once, and it can be renamed and deleted', async ({ page, request }) => {
  const agent = await newAgent(request, unique('Token agent'))
  const name = unique('Telegram bot')
  try {
    await page.goto('/tokens')
    await expect(row(page, 'initial')).toContainText('owner') // the token of INITIAL_API_KEY
    await page.getByRole('button', { name: 'New token' }).click()
    const create = dialog(page, 'New token')
    await expect(create.getByRole('button', { name: 'Create' })).toBeDisabled() // a name is required
    await field(create, 'Name').getByRole('textbox').fill('   ')
    await expect(create.getByRole('button', { name: 'Create' })).toBeDisabled() // blank is no name
    await field(create, 'Name').getByRole('textbox').fill(name)
    await field(create, 'Role').getByRole('combobox').click()
    await expect(page.getByRole('option', { name: /^user/ })).toContainText('prompt, knowledge base') // what the role means is on its card
    await page.getByRole('option', { name: /^user/ }).click()
    await expect(field(create, 'Role').getByRole('combobox')).toContainText('user')
    await field(create, 'Agent').getByRole('combobox').click()
    await chooseCard(page, agent.name)
    await create.getByRole('button', { name: 'Create' }).click()

    // shown once, here
    const secret = dialog(page, 'Copy the token now')
    await expect(secret).toContainText('only here, once')
    const code = secret.getByTestId('new-token')
    await expect(code).toHaveText(/^[A-Za-z0-9_]{64}$/)
    const shown = (await code.innerText()).trim()
    await secret.getByRole('button', { name: 'Copy token' }).click()
    const me = await (await request.get('/api/v1/tokens/self', { headers: { Authorization: `Bearer ${shown}` } })).json()
    expect(me).toMatchObject({ name, role: 'user', agent_id: agent.id })
    await closeSecret(page)

    // listed with its role and agent, and never with the secret
    await expect(row(page, name)).toContainText('user')
    await expect(row(page, name)).toContainText(agent.name)
    await page.reload()
    await expect(row(page, name)).toBeVisible()
    await expect(page.getByText(shown)).toHaveCount(0)
    expect(await page.content()).not.toContain(shown)

    // edited: the name and the role can change (the agent cannot)
    await row(page, name).getByRole('button', { name: 'Edit' }).click()
    const edit = dialog(page, `Token “${name}”`)
    await expect(edit.getByRole('button', { name: 'Save' })).toBeDisabled() // nothing changed yet
    await expect(field(edit, 'Role').getByRole('combobox')).toContainText('user')
    await field(edit, 'Name').getByRole('textbox').fill(`${name} v2`)
    await field(edit, 'Role').getByRole('combobox').click()
    await page.getByRole('option', { name: /^regular/ }).click()
    await edit.getByRole('button', { name: 'Save' }).click()
    await expect(toast(page, 'Token updated')).toBeVisible()
    await expect(row(page, `${name} v2`)).toContainText('regular')
    const lowered = await (await request.get('/api/v1/tokens/self', { headers: { Authorization: `Bearer ${shown}` } })).json()
    expect(lowered).toMatchObject({ role: 'regular', agent_id: agent.id }) // the same secret, the new role

    // deleted: it stops working at once
    await row(page, `${name} v2`).getByRole('button', { name: 'Delete' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click()
    await expect(toast(page, 'Token deleted')).toBeVisible()
    await expect(row(page, `${name} v2`)).toHaveCount(0)
    const after = await request.get('/api/v1/tokens/self', { headers: { Authorization: `Bearer ${shown}` } })
    expect(after.status()).toBe(403)
  } finally {
    await dropAgent(request, agent.id)
  }
})

test('the token in use and the initial token cannot be deleted from the panel', async ({ page }) => {
  await page.goto('/tokens')
  const initial = row(page, 'initial')
  await expect(initial).toContainText('you')
  await expect(initial).toContainText('initial')
  await expect(initial.getByRole('button', { name: 'Delete' })).toBeDisabled()
})

test('a token whose agent has tokens keeps the agent from being deleted', async ({ page, request }) => {
  const agent = await newAgent(request)
  try {
    await page.goto('/tokens')
    await page.getByRole('button', { name: 'New token' }).click()
    const create = dialog(page, 'New token')
    await field(create, 'Name').getByRole('textbox').fill('holder')
    await field(create, 'Agent').getByRole('combobox').click()
    await chooseCard(page, agent.name)
    await create.getByRole('button', { name: 'Create' }).click()
    await closeSecret(page)

    await page.goto('/agents')
    await row(page, agent.name).getByRole('button', { name: 'Delete' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click()
    await expect(toast(page, /still has tokens/)).toBeVisible()
  } finally {
    await dropAgent(request, agent.id)
  }
})

test('the role of the token in use and of the initial token is not offered for change', async ({ page }) => {
  await page.goto('/tokens')
  await row(page, 'initial').getByRole('button', { name: 'Edit' }).click()
  const edit = dialog(page, /^Token/)
  await expect(field(edit, 'Role').getByRole('combobox')).toBeDisabled()
  await expect(field(edit, 'Role')).toContainText('stays an owner')
})

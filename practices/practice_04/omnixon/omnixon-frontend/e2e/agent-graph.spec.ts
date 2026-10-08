import { AUTH, chooseCard, dialog, dropAgent, expect, field, newAgent, test, toast, unique } from './fixtures'

test('connections are made, shown as arrows, changed and deleted in the graph', async ({ page, request }) => {
  const a = await newAgent(request, unique('Caller'))
  const b = await newAgent(request, unique('Called'))
  try {
    await page.goto('/agent-graph')
    await expect(page.getByTestId(`agent-node-${a.id}`)).toBeVisible()
    await expect(page.getByTestId(`agent-node-${b.id}`)).toBeVisible()

    await page.getByRole('button', { name: 'Add connection' }).click()
    const create = dialog(page, 'New connection')
    await field(create, 'Calling agent').getByRole('combobox').click()
    await chooseCard(page, a.name)
    await field(create, 'Called agent').getByRole('combobox').click()
    await chooseCard(page, b.name)
    await field(create, 'Description').getByRole('textbox').fill('Knows the prices of everything in the shop')
    await create.getByRole('button', { name: 'Connect' }).click()
    await expect(toast(page, 'Connection created')).toBeVisible()

    const made = (await (await request.get('/api/v1/admin/agent-connections', { headers: AUTH, params: { agent_id: a.id } })).json())[0]
    const label = page.getByTestId(`edge-label-${made.id}`)
    await expect(label).toHaveText('Knows the prices of everyth...') // 30 characters on the arrow
    await expect(label).toHaveAttribute('title', 'Knows the prices of everything in the shop')

    await label.click()
    const edit = dialog(page, `${a.name} → ${b.name}`)
    await expect(field(edit, 'Description').getByRole('textbox')).toHaveValue('Knows the prices of everything in the shop')
    await field(edit, 'Description').getByRole('textbox').fill('Knows stock')
    await edit.getByRole('button', { name: 'Save' }).click()
    await expect(toast(page, 'Connection updated')).toBeVisible()
    await expect(label).toHaveText('Knows stock')

    await label.click()
    await dialog(page, `${a.name} → ${b.name}`).getByRole('button', { name: 'Delete' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click()
    await expect(toast(page, 'Connection deleted')).toBeVisible()
    await expect(label).toHaveCount(0)
  } finally {
    await dropAgent(request, a.id)
    await dropAgent(request, b.id)
  }
})

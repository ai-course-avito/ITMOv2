import { dialog, expect, field, nameBox, row, test, toast, unique } from './fixtures'

test('MCP server: create, attach to an agent, detach, edit, delete', async ({ page }) => {
  const host = unique('mcp').replace(/[^a-z0-9]/g, '')
  const url = `http://${host}:9100/mcp`
  const label = unique('Maths tools')

  await page.goto('/mcp-servers')
  await page.getByRole('button', { name: 'New server' }).click()
  const create = dialog(page, 'New MCP server')
  await expect(create.getByRole('button', { name: 'Save' })).toBeDisabled() // a name is required
  await field(create, 'URL').getByRole('textbox').fill(url)
  await expect(create.getByRole('button', { name: 'Save' })).toBeDisabled()
  await nameBox(create).fill(label)
  await field(create, 'Other options (JSON)').getByRole('textbox').fill('{"timeout": 3}')
  await create.getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'MCP server created')).toBeVisible()
  await expect(row(page, url)).toContainText('timeout')
  await expect(row(page, url)).toContainText(label)

  // attach it to the unit's own agent (#1, the seeded one)
  await page.goto('/agents/1')
  await page.getByRole('tab', { name: 'MCP servers' }).click()
  await field(page, 'Attach a server').getByRole('combobox').click()
  await expect(page.getByRole('option', { name: new RegExp(host) })).toContainText(label) // the card is called by its name
  await page.getByRole('option', { name: new RegExp(host) }).click()
  await page.getByRole('button', { name: 'Attach', exact: true }).click()
  await expect(toast(page, 'Attached')).toBeVisible()
  await expect(row(page, url)).toBeVisible()

  await page.getByRole('tab', { name: 'Versions' }).click()
  await expect(row(page, /MCP server \d+ attached/)).toBeVisible()
  await page.getByRole('tab', { name: 'MCP servers' }).click()

  await row(page, url).getByRole('button', { name: 'Detach' }).click()
  await expect(toast(page, 'Detached')).toBeVisible()
  await expect(row(page, url)).toHaveCount(0)

  // edit and delete on the MCP servers page
  await page.goto('/mcp-servers')
  await row(page, url).getByRole('button', { name: 'Edit' }).click()
  const edit = dialog(page, `MCP server “${label}”`)
  await expect(nameBox(edit)).toHaveValue(label)
  await expect(field(edit, 'URL').getByRole('textbox')).toHaveValue(url)
  await nameBox(edit).fill(`${label} 2`)
  await field(edit, 'Transport').getByRole('combobox').click()
  await page.getByRole('option', { name: 'sse' }).click()
  await edit.getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'MCP server updated')).toBeVisible()
  await expect(row(page, url)).toContainText('sse')
  await expect(row(page, url)).toContainText(`${label} 2`)

  await row(page, url).getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click()
  await expect(toast(page, 'MCP server deleted')).toBeVisible()
  await expect(row(page, url)).toHaveCount(0)
})

test('the service rejects an unknown MCP option', async ({ page }) => {
  await page.goto('/mcp-servers')
  await page.getByRole('button', { name: 'New server' }).click()
  const create = dialog(page, 'New MCP server')
  await nameBox(create).fill('Bogus')
  await field(create, 'URL').getByRole('textbox').fill('http://x:1/mcp')
  await field(create, 'Other options (JSON)').getByRole('textbox').fill('{"bogus": 1}')
  await create.getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, /Unknown options: bogus/)).toBeVisible()
})

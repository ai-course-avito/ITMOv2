import { dialog, expect, field, nameBox, row, test, toast, unique } from './fixtures'

test('agent lifecycle: create, edit, versions, view, compare, roll back, delete', async ({ page }) => {
  const label = unique('Pirate bot')
  const first = unique('You are pirate')
  const second = unique('You are wizard')

  // create
  await page.goto('/agents')
  await page.getByRole('button', { name: 'New agent' }).click()
  const create = dialog(page, 'New agent')
  await expect(create.getByRole('button', { name: 'Create' })).toBeDisabled() // a name is required
  await nameBox(create).fill(label)
  await field(create, 'System prompt').getByRole('textbox').fill(first)
  await field(create, 'Message limit').getByRole('spinbutton').fill('4')
  await field(create, 'Knowledge limit').getByRole('spinbutton').fill('12')
  await create.getByRole('button', { name: 'Create' }).click()
  await expect(page).toHaveURL(/\/agents\/\d+$/)
  await expect(page.getByRole('heading', { name: label })).toBeVisible() // the page is called by the name
  await expect(page.getByRole('navigation', { name: /breadcrumb/i })).toContainText(label)

  // edit from the page: the form shows what was saved, then saves a change with a comment
  const prompt = field(page, 'System prompt').getByRole('textbox')
  await expect(prompt).toHaveValue(first)
  await expect(field(page, 'Message limit').getByRole('spinbutton')).toHaveValue('4')
  await expect(field(page, 'Knowledge limit').getByRole('spinbutton')).toHaveValue('12') // config.rag_limit
  await expect(nameBox(page)).toHaveValue(label)
  await prompt.fill(second)
  await field(page, 'Comment').getByRole('textbox').fill('made it a wizard')
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(toast(page, 'Agent saved')).toBeVisible()

  // versions
  await page.getByRole('tab', { name: 'Versions' }).click()
  await expect(row(page, 'made it a wizard')).toContainText('latest')
  await expect(row(page, 'created')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Roll back to version 2' })).toBeDisabled() // the latest one

  // view a past version: its prompt, and the neighbours
  await page.getByRole('button', { name: 'View version 1' }).click()
  const viewer = dialog(page, /Version 1/)
  await expect(viewer.getByText(first)).toBeVisible()
  await expect(viewer.getByRole('button', { name: 'Older' })).toBeDisabled()
  await viewer.getByRole('button', { name: 'Newer' }).click()
  await expect(dialog(page, /Version 2/)).toContainText(second)
  await dialog(page, /Version 2/).getByRole('button', { name: 'Older' }).click()
  await expect(dialog(page, /Version 1/)).toContainText(first)

  // its changes against the current one
  await dialog(page, /Version 1/).getByRole('tab', { name: 'Changes' }).click()
  await expect(dialog(page, /Version 1/).getByText(second)).toBeVisible()
  await dialog(page, /Version 1/).getByRole('tab', { name: 'JSON' }).click()
  await expect(dialog(page, /Version 1/).getByText('"prompt"')).toBeVisible()

  // roll back from inside the viewer
  await dialog(page, /Version 1/).getByRole('button', { name: 'Roll back to this version' }).click()
  await dialog(page, 'Roll back to version 1?').getByRole('button', { name: 'Roll back' }).click()
  await expect(toast(page, 'recorded as version 3')).toBeVisible()
  await expect(row(page, 'rolled back to version 1')).toContainText('latest')

  await page.getByRole('tab', { name: 'Settings' }).click()
  await expect(field(page, 'System prompt').getByRole('textbox')).toHaveValue(first)

  // and once more from the row button, then compare from the row
  await page.getByRole('tab', { name: 'Versions' }).click()
  await page.getByRole('button', { name: 'Compare version 2' }).click()
  await expect(dialog(page, /Version 2/).getByRole('tab', { name: 'Changes', selected: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: 'Roll back to version 2' }).click()
  await dialog(page, 'Roll back to version 2?').getByRole('button', { name: 'Roll back' }).click()
  await expect(toast(page, 'recorded as version 4')).toBeVisible()
  await page.getByRole('tab', { name: 'Settings' }).click()
  await expect(field(page, 'System prompt').getByRole('textbox')).toHaveValue(second)

  // delete from the list
  await page.goto('/agents')
  await row(page, second).getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click()
  await expect(toast(page, 'Agent deleted')).toBeVisible()
  await expect(row(page, second)).toHaveCount(0)
})


test('edit and duplicate an agent from the list, with its MCP servers', async ({ page }) => {
  const host = unique('mcp').replace(/[^a-z0-9]/g, '')
  const url = `http://${host}:9100/mcp`
  const prompt = unique('list agent')
  const name = unique('Listed')

  await page.goto('/mcp-servers')
  await page.getByRole('button', { name: 'New server' }).click()
  await nameBox(dialog(page, 'New MCP server')).fill(unique('Tools'))
  await field(dialog(page, 'New MCP server'), 'URL').getByRole('textbox').fill(url)
  await dialog(page, 'New MCP server').getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'MCP server created')).toBeVisible()

  // create with the MCP server ticked
  await page.goto('/agents')
  await page.getByRole('button', { name: 'New agent' }).click()
  const create = dialog(page, 'New agent')
  await nameBox(create).fill(name)
  await field(create, 'System prompt').getByRole('textbox').fill(prompt)
  await create.getByRole('checkbox', { name: new RegExp(host) }).check()
  await create.getByRole('button', { name: 'Create' }).click()
  await expect(page).toHaveURL(/\/agents\/\d+$/)
  const agentId = page.url().match(/agents\/(\d+)$/)![1]
  await page.getByRole('tab', { name: 'MCP servers' }).click()
  await expect(row(page, url)).toBeVisible()

  // edit from the list: change the prompt, untick the server
  await page.goto('/agents')
  await row(page, prompt).getByRole('button', { name: 'Edit' }).click()
  const edit = dialog(page, `Edit agent “${name}”`)
  await expect(field(edit, 'System prompt').getByRole('textbox')).toHaveValue(prompt)
  await expect(edit.getByRole('checkbox', { name: new RegExp(host) })).toBeChecked()
  await field(edit, 'System prompt').getByRole('textbox').fill(`${prompt} v2`)
  await edit.getByRole('checkbox', { name: new RegExp(host) }).uncheck()
  await edit.getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, `Agent “${name}” saved`)).toBeVisible()
  await expect(row(page, `${prompt} v2`)).toBeVisible()

  // duplicate it
  await row(page, `${prompt} v2`).getByRole('button', { name: 'Duplicate' }).click()
  const copy = dialog(page, `Duplicate agent “${name}”`)
  await expect(nameBox(copy)).toHaveValue(`${name} (copy)`)
  await expect(field(copy, 'System prompt').getByRole('textbox')).toHaveValue(`${prompt} v2`)
  await copy.getByRole('button', { name: 'Create' }).click()
  await expect(page).toHaveURL(/\/agents\/\d+$/)
  await expect(page.url().match(/agents\/(\d+)$/)![1]).not.toBe(agentId)

  // clean up: both agents and the server
  await page.goto('/agents')
  for (let i = 0; i < 2; i++) {
    await row(page, `${prompt} v2`).first().getByRole('button', { name: 'Delete' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click()
    await expect(toast(page, 'Agent deleted')).toBeVisible()
  }
  await page.goto('/mcp-servers')
  await row(page, url).getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click()
  await expect(toast(page, 'MCP server deleted')).toBeVisible()
})

test('an unknown agent shows the service error', async ({ page }) => {
  await page.goto('/agents/999999')
  await expect(page.getByText('Request failed')).toBeVisible()
  await expect(page.getByText('Agent not found')).toBeVisible()
})

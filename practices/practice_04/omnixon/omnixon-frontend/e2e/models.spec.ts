import { AUTH, dialog, expect, field, nameBox, row, test, toast, unique } from './fixtures'

test('create, edit, duplicate and delete a model; the default one is protected', async ({ page }) => {
  const name = unique('e2e/model')
  const label = unique('Fast one')
  await page.goto('/models')

  // the default model was made before names existed: it shows its own model name as its name
  await expect(row(page, 'default')).toBeVisible()
  await expect(row(page, 'default').getByRole('cell').nth(1)).toContainText(/\w\/\w/)
  await expect(row(page, 'default').getByRole('button', { name: 'Delete' })).toBeDisabled()

  // create with structured fields
  await page.getByRole('button', { name: 'New model' }).click()
  const create = dialog(page, 'New model')
  await nameBox(create).fill(label)
  await field(create, 'Model').getByRole('textbox').fill(name)
  await field(create, 'Temperature').getByRole('textbox').fill('0.3')
  await field(create, 'Other options (JSON)').getByRole('textbox').fill('{"reasoning": {"effort": "low"}}')
  await create.getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'Model created')).toBeVisible()
  await expect(row(page, label)).toContainText(name) // the name and the model's own name are both shown
  // the Settings cell shows 40 characters at most; the whole JSON is its tooltip
  const settings = row(page, name).locator('span[title*="temperature"]')
  await expect(settings).toHaveAttribute('title', /"temperature":0\.3/)
  await expect(settings).toHaveAttribute('title', /reasoning/)

  // edit: the form shows what was stored; change a field and the JSON
  await row(page, name).getByRole('button', { name: 'Edit' }).click()
  const edit = dialog(page, `Model “${label}”`)
  await expect(nameBox(edit)).toHaveValue(label)
  await expect(field(edit, 'Model').getByRole('textbox')).toHaveValue(name)
  await expect(field(edit, 'Temperature').getByRole('textbox')).toHaveValue('0.3')
  await field(edit, 'Temperature').getByRole('textbox').fill('')
  await field(edit, 'Top P').getByRole('textbox').fill('0.5')
  await edit.getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'Model updated')).toBeVisible()
  const changed = row(page, name).locator('span[title*="top_p"]') // the whole settings, not the 40 shown
  await expect(changed).toBeVisible()
  await expect(changed).not.toHaveAttribute('title', /temperature/)

  // rename: the name changes, the model does not
  await row(page, name).getByRole('button', { name: 'Edit' }).click()
  await nameBox(dialog(page, `Model “${label}”`)).fill(`${label} v2`)
  await dialog(page, `Model “${label}”`).getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'Model updated')).toBeVisible()
  await expect(row(page, `${label} v2`)).toContainText(name)

  // duplicate starts from a copy, saved as a new record
  await row(page, name).getByRole('button', { name: 'Duplicate' }).click()
  const copy = dialog(page, 'New model')
  await expect(nameBox(copy)).toHaveValue(`${label} v2 (copy)`)
  await expect(field(copy, 'Model').getByRole('textbox')).toHaveValue(name)
  await field(copy, 'Model').getByRole('textbox').fill(`${name}-copy`)
  await copy.getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'Model created')).toBeVisible()

  for (const n of [`${name}-copy`, name]) {
    await row(page, n).getByRole('button', { name: 'Delete' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click()
    await expect(toast(page, 'Model deleted')).toBeVisible()
    await expect(row(page, n)).toHaveCount(0)
  }
})

test('a model needs a name and a model, and bad JSON is reported', async ({ page }) => {
  await page.goto('/models')
  await page.getByRole('button', { name: 'New model' }).click()
  const create = dialog(page, 'New model')
  await expect(create.getByRole('button', { name: 'Save' })).toBeDisabled()
  await field(create, 'Model').getByRole('textbox').fill('a/b')
  await expect(create.getByRole('button', { name: 'Save' })).toBeDisabled() // the model alone is not enough
  await nameBox(create).fill('   ')
  await expect(create.getByRole('button', { name: 'Save' })).toBeDisabled() // blank is no name
  await nameBox(create).fill('Named')
  await expect(create.getByRole('button', { name: 'Save' })).toBeEnabled()
  await field(create, 'Other options (JSON)').getByRole('textbox').fill('{broken')
  await expect(create.getByRole('button', { name: 'Save' })).toBeDisabled()
})

test('the table searches and sorts', async ({ page }) => {
  await page.goto('/models')
  await page.getByLabel('Search the table').fill('zzz-nothing-matches')
  await expect(page.getByText('No results.')).toBeVisible()
  await page.getByLabel('Search the table').fill('')
  await expect(row(page, 'default')).toBeVisible()
  await page.getByRole('button', { name: 'ID', exact: true }).click()
  await expect(page.getByRole('columnheader', { name: 'Name' })).toBeVisible()
  await page.getByRole('button', { name: 'Columns' }).click()
  await page.getByRole('menuitemcheckbox', { name: 'Settings' }).click()
  await expect(page.getByRole('columnheader', { name: 'Settings' })).toHaveCount(0)
})

test('external model settings are hidden until the list is opened, and the key is never shown again', async ({
  page,
  request,
}) => {
  const name = unique('fake/pong-ext')
  const label = unique('External')
  await page.goto('/models')
  await page.getByRole('button', { name: 'New model' }).click()
  const create = dialog(page, 'New model')

  // closed by default: nothing about the connection is in the form
  const toggle = create.getByRole('button', { name: 'External model settings' })
  await expect(toggle).toBeVisible()
  await expect(field(create, 'Base URL')).toHaveCount(0)
  await expect(create.getByRole('switch', { name: 'Use proxy' })).toHaveCount(0)
  await expect(field(create, 'API token')).toHaveCount(0)

  await nameBox(create).fill(label)
  await field(create, 'Model').getByRole('textbox').fill(name)
  await toggle.click()
  await expect(field(create, 'Base URL').getByRole('textbox')).toHaveAttribute(
    'placeholder',
    'https://openrouter.ai/api/v1',
  )
  await expect(create.getByRole('switch', { name: 'Use proxy' })).toBeChecked() // on by default
  await expect(field(create, 'API token').locator('input')).toHaveAttribute('type', 'password')
  await field(create, 'Base URL').getByRole('textbox').fill('http://fake-llm:8000/v1')
  await create.getByRole('switch', { name: 'Use proxy' }).click()
  await field(create, 'API token').locator('input').fill('sk-e2e-secret-key')
  await create.getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'Model created')).toBeVisible()

  // what is stored: the connection, and a key that the service never gives back
  const stored = (await (await request.get('/api/v1/admin/models', { headers: AUTH })).json()).find(
    (m: { name: string }) => m.name === label,
  )
  expect(stored).toMatchObject({ base_url: 'http://fake-llm:8000/v1', use_proxy: false, has_api_token: true })
  expect(JSON.stringify(stored)).not.toContain('sk-e2e-secret-key')
  await expect(row(page, label)).toContainText('fake-llm:8000') // the table says it is not OpenRouter
  await expect(row(page, label)).toContainText('no proxy')

  // edit: closed again; the fields show what is stored, the key only as "set"
  await row(page, label).getByRole('button', { name: 'Edit' }).click()
  const edit = dialog(page, `Model “${label}”`)
  await expect(field(edit, 'Base URL')).toHaveCount(0)
  await edit.getByRole('button', { name: 'External model settings' }).click()
  await expect(field(edit, 'Base URL').getByRole('textbox')).toHaveValue('http://fake-llm:8000/v1')
  await expect(edit.getByRole('switch', { name: 'Use proxy' })).not.toBeChecked()
  await expect(field(edit, 'API token').locator('input')).toHaveValue('')
  await expect(field(edit, 'API token')).toContainText('has a key of its own')

  // clear the key and go back to OpenRouter: only the connection changes
  await edit.getByRole('button', { name: 'Remove the key of this model' }).click()
  await field(edit, 'Base URL').getByRole('textbox').click()
  await page.keyboard.press('ControlOrMeta+A') // cleared as a person would: select it all and delete it
  await page.keyboard.press('Backspace')
  await edit.getByRole('switch', { name: 'Use proxy' }).click()
  await expect(field(edit, 'Base URL').getByRole('textbox')).toHaveValue('') // the form has taken all three changes before it is saved
  await expect(edit.getByRole('switch', { name: 'Use proxy' })).toBeChecked()
  await expect(field(edit, 'API token')).toContainText('will be removed')
  await edit.getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'Model updated')).toBeVisible()
  const after = await (await request.get(`/api/v1/admin/models/${stored.id}`, { headers: AUTH })).json()
  expect(after).toMatchObject({ base_url: 'https://openrouter.ai/api/v1', use_proxy: true, has_api_token: false })
  expect(after.request_json).toEqual({ model: name })

  await row(page, label).getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click()
  await expect(toast(page, 'Model deleted')).toBeVisible()
})

test('a base URL that is not an address is refused by the service and says so', async ({ page }) => {
  await page.goto('/models')
  await page.getByRole('button', { name: 'New model' }).click()
  const create = dialog(page, 'New model')
  await nameBox(create).fill(unique('Bad url'))
  await field(create, 'Model').getByRole('textbox').fill('a/b')
  await create.getByRole('button', { name: 'External model settings' }).click()
  await field(create, 'Base URL').getByRole('textbox').fill('not a url')
  await create.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText(/base_url must be an http\(s\) address/i)).toBeVisible()
})

test('the box for the other options holds what is typed in it without scrolling', async ({ page }) => {
  await page.goto('/models')
  await page.getByRole('button', { name: 'New model' }).click()
  const box = field(dialog(page, 'New model'), 'Other options (JSON)').getByRole('textbox')
  const text = '{\n  "reasoning": {"effort": "low"},\n  "stop": ["END"]\n}'
  await box.fill(text)
  const { scroll, client } = await box.evaluate((el) => ({ scroll: el.scrollHeight, client: el.clientHeight }))
  expect(scroll).toBeLessThanOrEqual(client) // nothing is hidden below the edge
  expect((await box.boundingBox())!.height).toBeGreaterThanOrEqual(120)
})

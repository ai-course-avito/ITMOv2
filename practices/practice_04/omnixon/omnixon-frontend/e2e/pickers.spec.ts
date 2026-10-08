import { AUTH, closeSettings, dialog, openSettings, dropAgent, expect, field, newAgent, optionWithId, test, unique } from './fixtures'

/** The agent picker of the "New token" dialog: a list of agent cards. */
async function openAgentPicker(page: import('@playwright/test').Page) {
  await page.goto('/tokens')
  await page.getByRole('button', { name: 'New token' }).click()
  const agent = field(dialog(page, 'New token'), 'Agent').getByRole('combobox')
  await agent.click()
  return agent
}

test('choices are cards: an icon, a name, an id, and what belongs to them as links', async ({ page }) => {
  const agent = await openAgentPicker(page)

  // the agent of the initial token: made without a prompt, named "Default agent"
  const seeded = optionWithId(page, 1)
  await expect(seeded).toContainText('Default agent')
  await expect(seeded).toContainText('no prompt') // its prompt (here empty) is shown beside the name
  await expect(seeded.locator('span.value-mono', { hasText: /^1$/ })).toBeVisible() // the id badge
  await expect(seeded.getByText('rag', { exact: true })).toHaveCount(0) // the tools of an agent are not on its card
  await expect(seeded.getByText('memory', { exact: true })).toHaveCount(0)
  // the model of the agent is a link to that model, not text with a separator
  const model = seeded.getByRole('link', { name: 'openai/gpt-4o-mini' })
  await expect(model).toHaveAttribute('href', /\/models\?open=\d+$/)
  await expect(seeded.getByRole('link', { name: 'Open Default agent' })).toHaveAttribute('href', '/agents/1')

  // choosing a card leaves a small card in the field, not text, with a link to open the agent
  await seeded.getByText('Default agent', { exact: true }).click()
  await expect(agent).toContainText('Default agent')
  await expect(agent.locator('span.value-mono', { hasText: /^1$/ })).toBeVisible()
  await expect(field(dialog(page, 'New token'), 'Agent').getByRole('link', { name: 'Open Default agent' })).toHaveAttribute('href', '/agents/1')
  await expect(page.locator('[data-slot=dialog-content] input[data-slot=input-group-control]')).toHaveCount(0) // no plain text box

  // the search on top finds a card by its id
  await agent.click()
  await page.getByPlaceholder('Search…').fill('zzzz')
  await expect(page.getByText('Nothing found.')).toBeVisible()
})

test('a link inside a card goes to the related entity and does not pick the card', async ({ page }) => {
  await openAgentPicker(page)
  await optionWithId(page, 1).getByRole('link', { name: 'openai/gpt-4o-mini' }).click()

  // the models page opens the editor of that model
  await expect(page).toHaveURL(/\/models$/)
  await expect(dialog(page, /Model/)).toBeVisible()
  await expect(field(page, 'Model').getByRole('textbox')).toHaveValue('openai/gpt-4o-mini')
})

test('a long attribute is shown whole on a second row instead of being cut to one line', async ({ page, request }) => {
  const prompt = 'You are a very careful assistant who always answers in complete sentences and never guesses'
  const agent = await newAgent(request, unique('Wordy'), { prompt })
  try {
    await openAgentPicker(page)
    const card = optionWithId(page, agent.id)
    await expect(card).toContainText('You are a very careful assistant')
    const prompts = card.getByText(/You are a very careful assistant/)
    const chip = (await prompts.boundingBox())!
    const title = (await card.getByText(agent.name, { exact: true }).boundingBox())!
    expect(chip.y).toBeGreaterThan(title.y) // under the name, on its own row
    // whole: not cut by an ellipsis or by the card (the text fits the two lines it is given)
    expect(await prompts.evaluate((el) => el.scrollHeight <= el.clientHeight + 1)).toBe(true)
    // the model chip is there as well, and not cut off by the prompt
    await expect(card.getByRole('link', { name: 'openai/gpt-4o-mini' })).toBeVisible()
  } finally {
    await dropAgent(request, agent.id)
  }
})

test('the card of a token leads to its agent', async ({ page }) => {
  await page.goto('/usage')
  await page.getByRole('group', { name: 'Token', exact: true }).getByRole('combobox').click()
  const token = page.getByRole('option').filter({ hasText: 'initial' })
  await expect(token).toContainText('owner')
  await expect(token.getByRole('link', { name: 'Default agent' })).toHaveAttribute('href', '/agents/1')
  await token.getByRole('link', { name: 'Default agent' }).click()
  await expect(page).toHaveURL(/\/agents\/1$/)
})

test('the playground starts on your agent and suggests its users after 3 characters, per agent', async ({ page, request }) => {
  const prefix = unique('sgx').replace(/[^a-z0-9]/g, '')
  const mine = [`${prefix}-alpha`, `${prefix}-beta`]
  for (const external_id of mine) await request.post('/api/v1/users', { headers: AUTH, data: { external_id } })
  const other = await newAgent(request, unique('Other'))

  try {
    await page.goto('/chat')
    const settings = await openSettings(page)
    const user = field(settings, 'User id').getByRole('combobox')

    // your own agent is chosen already, so the box works at once
    await expect(field(settings, 'Agent').getByRole('combobox')).toContainText('Default agent')
    await expect(user).toBeEnabled()
    await expect(page.getByPlaceholder('Message…')).toBeVisible()

    // fewer than 3 characters: no search, just a hint
    await user.fill(prefix.slice(0, 2))
    await expect(page.getByText('Type at least 3 characters to search')).toBeVisible()

    // 3 or more: the users of this agent whose id starts with it, as cards
    await user.fill(prefix)
    const options = page.getByRole('option')
    await expect(options).toHaveCount(2)
    await expect(options.first()).toContainText(`${prefix}-alpha`)
    await expect(options.first()).toContainText('created')
    await options.first().click()
    await expect(user).toHaveValue(`${prefix}-alpha`)

    // nothing starts with this: the id is still fine to use, the service creates the user
    await user.fill(`${prefix}-zzz`)
    await expect(page.getByText(`No users start with “${prefix}-zzz”`)).toBeVisible()
    await expect(user).toHaveValue(`${prefix}-zzz`)

    // ids differ from agent to agent: choosing another agent empties the box
    await user.fill(`${prefix}-alpha`)
    await page.keyboard.press('Escape') // close the suggestions; a click elsewhere would only close them
    await field(settings, 'Agent').getByRole('combobox').click()
    await optionWithId(page, other.id).locator('.font-medium').first().click()
    await expect(user).toHaveValue('')
    await user.fill(prefix) // that agent has none of them
    await expect(page.getByText(`No users start with “${prefix}”`)).toBeVisible()
    void closeSettings
  } finally {
    for (const external_id of mine) await request.delete(`/api/v1/users/${external_id}`, { headers: AUTH })
    await dropAgent(request, other.id)
  }
})

test('the users page suggests too, from the agent of the token', async ({ page, request }) => {
  const prefix = unique('sgy').replace(/[^a-z0-9]/g, '')
  await request.post('/api/v1/users', { headers: AUTH, data: { external_id: `${prefix}-one` } })
  try {
    await page.goto('/users')
    await field(page, 'External id').getByRole('combobox').fill(prefix)
    await expect(page.getByRole('option')).toHaveCount(1)
    await expect(page.getByRole('option')).toContainText(`${prefix}-one`)
  } finally {
    await request.delete(`/api/v1/users/${prefix}-one`, { headers: AUTH })
  }
})

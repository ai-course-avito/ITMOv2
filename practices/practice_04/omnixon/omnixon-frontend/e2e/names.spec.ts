import { AUTH, dialog, expect, field, newToken, optionWithId, row, test, unique } from './fixtures'

// Entities are called by the name people gave them, everywhere; the technical value (a model's own name, the
// start of a prompt, an MCP url) is shown beside it, never instead of it.

test('names are shown in tables, cards and pages, with the technical value beside them', async ({ page, request }) => {
  const agentName = unique('Support bot')
  const prompt = 'You answer questions about refunds. Always be polite.'
  const modelName = unique('Quick')
  const modelId = `e2e/${unique('m').replace(/[^a-z0-9]/g, '')}`
  const mcpName = unique('Calc')
  const mcpUrl = `http://${unique('h').replace(/[^a-z0-9]/g, '')}:9100/mcp`
  const tokenName = unique('Telegram')

  const model = await (await request.post('/api/v1/admin/models', { headers: AUTH, data: { name: modelName, request_json: { model: modelId } } })).json()
  const mcp = await (await request.post('/api/v1/admin/mcp-servers', { headers: AUTH, data: { name: mcpName, config: { url: mcpUrl } } })).json()
  const agent = await (await request.post('/api/v1/admin/agents', { headers: AUTH, data: { name: agentName, prompt, model_id: model.id } })).json()
  const token = await newToken(request, agent.id, 'user', tokenName)
  try {
    // tables
    await page.goto('/agents')
    await expect(row(page, agentName)).toContainText('You answer questions about refunds')
    await expect(row(page, agentName)).toContainText(modelId) // the model column is the model's own name
    await page.goto('/models')
    await expect(row(page, modelName)).toContainText(modelId)
    await page.goto('/mcp-servers')
    await expect(row(page, mcpName)).toContainText(mcpUrl)
    await page.goto('/tokens')
    await expect(row(page, tokenName)).toContainText(agentName) // the agent column is the agent's name, not its number
    await expect(row(page, tokenName)).toContainText('user')

    // the page of an agent is called by its name, also in the breadcrumb
    await page.goto(`/agents/${agent.id}`)
    await expect(page.getByRole('heading', { name: agentName })).toBeVisible()
    await expect(page.getByRole('navigation', { name: /breadcrumb/i })).toContainText(agentName)

    // an agent card: name, the start of the prompt, the model (by its own name, a link) and the id
    await page.goto('/tokens')
    await page.getByRole('button', { name: 'New token' }).click()
    await field(dialog(page, 'New token'), 'Agent').getByRole('combobox').click()
    const agentCard = optionWithId(page, agent.id)
    await expect(agentCard).toContainText(agentName)
    await expect(agentCard).toContainText('You answer questions about refunds')
    await expect(agentCard.getByRole('link', { name: modelId })).toHaveAttribute('href', `/models?open=${model.id}`)
    await page.keyboard.press('Escape')
    await dialog(page, 'New token').getByRole('button', { name: 'Cancel' }).click()

    // a model card (in the agent form): name and the model's own name
    await page.goto('/agents')
    await page.getByRole('button', { name: 'New agent' }).click()
    await field(dialog(page, 'New agent'), 'Model').getByRole('combobox').click()
    const modelCard = optionWithId(page, model.id)
    await expect(modelCard).toContainText(modelName)
    await expect(modelCard).toContainText(modelId)
    await page.keyboard.press('Escape')
    // the MCP checkbox is labelled by name and url
    await expect(dialog(page, 'New agent').getByRole('checkbox', { name: new RegExp(`${mcpName} .*${mcpUrl}`) })).toBeVisible()
    await dialog(page, 'New agent').getByRole('button', { name: 'Cancel' }).click()

    // an MCP card (attach picker): by name
    await page.goto(`/agents/${agent.id}`)
    await page.getByRole('tab', { name: 'MCP servers' }).click()
    await field(page, 'Attach a server').getByRole('combobox').click()
    const mcpCard = optionWithId(page, mcp.id)
    await expect(mcpCard).toContainText(mcpName)
    await expect(mcpCard).toContainText(mcpUrl)
    await page.keyboard.press('Escape')

    // a token card (the usage filter): the name, the role and the agent by name
    await page.goto('/usage')
    await page.getByRole('group', { name: 'Token', exact: true }).getByRole('combobox').click()
    const tokenCard = optionWithId(page, token.id)
    await expect(tokenCard).toContainText(tokenName)
    await expect(tokenCard).toContainText('user')
    await expect(tokenCard.getByRole('link', { name: agentName })).toHaveAttribute('href', `/agents/${agent.id}`)
  } finally {
    await request.delete(`/api/v1/admin/tokens/${token.id}`, { headers: AUTH })
    await request.delete(`/api/v1/admin/agents/${agent.id}`, { headers: AUTH })
    await request.delete(`/api/v1/admin/mcp-servers/${mcp.id}`, { headers: AUTH })
    await request.delete(`/api/v1/admin/models/${model.id}`, { headers: AUTH })
  }
})

test('entities made before names existed are called by their fallbacks', async ({ page }) => {
  // the seeded model was made before names existed: it is called by its own model name
  await page.goto('/models')
  await expect(row(page, 'default').getByRole('cell').nth(1)).toContainText(/\w\/\w/)
  // the agent of the initial token was named when it was made
  await page.goto('/agents')
  await expect(row(page, 'yours').getByRole('cell').nth(1)).toContainText('Default agent')
  await page.goto('/tokens')
  await expect(row(page, 'initial').getByRole('cell').nth(1)).toContainText('initial')
})

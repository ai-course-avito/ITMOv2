import { chooseCard, closeSecret, closeSettings, dialog, openSettings, dropAgent, expect, field, newAgent, newToken, row, signInAs, sidebar, test, toast, unique, AUTH } from './fixtures'

// What each role is offered, and what it can do, in the panel. The service decides what is allowed (tests.py in
// the service checks every endpoint for every role); here the panel must offer what works, hide what does not,
// and never knock on a door that is shut.

const ALL = ['Dashboard', 'Playground', 'Usage', 'Metrics', 'My agent', 'Agents', 'Models', 'MCP servers', 'Knowledge base', 'Memories', 'Users & history', 'Tokens', 'Settings']
const offered: Record<string, string[]> = {
  regular: ['Dashboard', 'Playground', 'Users & history', 'Settings'],
  user: ['Dashboard', 'Playground', 'Usage', 'My agent', 'Knowledge base', 'Memories', 'Users & history', 'Tokens', 'Settings'],
  admin: ['Dashboard', 'Playground', 'Usage', 'Metrics', 'Agents', 'Models', 'MCP servers', 'Knowledge base', 'Memories', 'Users & history', 'Tokens', 'Settings'],
  owner: ['Dashboard', 'Playground', 'Usage', 'Metrics', 'Agents', 'Models', 'MCP servers', 'Knowledge base', 'Memories', 'Users & history', 'Tokens', 'Settings'],
}

for (const role of ['regular', 'user', 'admin', 'owner'] as const) {
  test(`${role}: the menu offers what the role may use and the rest leads back to the dashboard`, async ({ browser, request }) => {
    const agent = await newAgent(request)
    const token = await newToken(request, agent.id, role, `${role} bot`)
    const { page, context } = await signInAs(browser, token.token)
    try {
      const nav = sidebar(page)
      // regular and user tokens start on the Playground (their own model is what they came to try); admin and owner on the dashboard
      const first = role === 'regular' || role === 'user' ? 'Playground' : 'Dashboard'
      await expect(page).toHaveURL(first === 'Playground' ? /\/chat$/ : /\/dashboard$/)
      await expect(page.getByRole('heading', { name: first })).toBeVisible()
      await page.goto('/')
      await expect(page).toHaveURL(first === 'Playground' ? /\/chat$/ : /\/dashboard$/) // and `/` leads there too
      // the dashboard is one click away in the sidebar for everyone
      await nav.getByRole('link', { name: 'Dashboard', exact: true }).click()
      await expect(page).toHaveURL(/\/dashboard$/)
      await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
      for (const item of ALL) {
        const link = nav.getByRole('link', { name: item, exact: true })
        if (offered[role].includes(item)) await expect(link, `${role} should be offered ${item}`).toBeVisible()
        else await expect(link, `${role} must not be offered ${item}`).toHaveCount(0)
      }
      // the account is called by the token and its role
      await expect(nav.getByRole('button', { name: new RegExp(`${role} bot`) })).toContainText(role)
      // a page that is not offered is not reachable by its address either
      for (const [item, path] of [['Agents', '/agents'], ['Models', '/models'], ['MCP servers', '/mcp-servers'], ['Metrics', '/metrics']] as const) {
        if (offered[role].includes(item)) continue
        await page.goto(path)
        await expect(page.getByRole('heading', { name: first }), `${role} opening ${path}`).toBeVisible() // back to where the role starts
      }
      if (role === 'regular') for (const path of ['/tokens', '/usage', '/rag', '/memories']) {
        await page.goto(path)
        await expect(page.getByRole('heading', { name: first }), `regular opening ${path}`).toBeVisible()
      }
    } finally {
      await context.close()
      await dropAgent(request, agent.id)
    }
  })
}

test('regular: the playground works as its own agent and the panel never calls /admin', async ({ browser, request }) => {
  const agent = await newAgent(request, unique('Plain agent'), { prompt: 'You are plain.' })
  const token = await newToken(request, agent.id, 'regular')
  const { page, context, adminCalls } = await signInAs(browser, token.token)
  try {
    await page.goto('/chat')
    const settings = await openSettings(page)
    const agentCard = field(settings, 'Agent')
    await expect(agentCard).toContainText(agent.name)
    await expect(agentCard.getByRole('combobox')).toHaveCount(0) // nothing to pick
    await expect(agentCard.getByRole('link')).toHaveCount(0) // and nothing it may open
    const ghost = unique('ghost').replace(/[^a-z0-9-]/g, '') // a user that does not exist yet: fine
    await field(settings, 'User id').getByRole('combobox').fill(ghost)
    await closeSettings(page)
    await page.getByPlaceholder(/Message…/).fill('hi')
    await page.getByRole('button', { name: 'Send' }).click()
    await expect(page.getByText(/Model provider error/)).toBeVisible() // no key in the test stack; the user part worked
    const made = await request.get(`/api/v1/users/${ghost}`, { headers: { Authorization: `Bearer ${token.token}` } })
    expect(made.status()).toBe(200)

    await page.goto('/settings')
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
    await page.goto('/dashboard')
    await expect(page.getByRole('main')).toContainText(token.name)
    await expect(page.getByRole('main').getByText('MCP servers')).toHaveCount(0) // no counters of admin lists
    expect(adminCalls).toEqual([])
    await request.delete(`/api/v1/users/${ghost}`, { headers: { Authorization: `Bearer ${token.token}` } })
  } finally {
    await context.close()
    await dropAgent(request, agent.id)
  }
})

test('user: edits its own agent, makes MCP servers for it and tokens for its clients, and stays on its own agent', async ({ browser, request }) => {
  const other = await newAgent(request, unique('Somebody else'))
  const agent = await newAgent(request, unique('Own agent'), { prompt: 'You are mine.' })
  const token = await newToken(request, agent.id, 'user', 'my user token')
  const { page, context } = await signInAs(browser, token.token)
  try {
    // "My agent" opens the agent page; another agent's address leads back to it
    await sidebar(page).getByRole('link', { name: 'My agent', exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`/agents/${agent.id}$`))
    await expect(page.getByRole('heading', { name: agent.name })).toBeVisible()
    await page.goto(`/agents/${other.id}`)
    await expect(page).toHaveURL(new RegExp(`/agents/${agent.id}$`))

    // it changes the prompt (and may pick a model from the list), with a version to show for it
    const prompt = field(page, 'System prompt').getByRole('textbox')
    await expect(prompt).toHaveValue('You are mine.')
    await prompt.fill('You are mine, and polite.')
    await field(page, 'Comment').getByRole('textbox').fill('by the user')
    await page.getByRole('button', { name: 'Save changes' }).click()
    await expect(toast(page, 'Agent saved')).toBeVisible()
    await page.getByRole('tab', { name: 'Versions' }).click()
    await expect(row(page, 'by the user')).toContainText('my user token') // made by this token
    await page.getByRole('tab', { name: 'Settings' }).click()
    await field(page, 'Model').getByRole('combobox').click()
    await expect(page.getByRole('option').first()).toBeVisible() // models can be read
    await page.keyboard.press('Escape')

    // an MCP server it makes belongs to its agent at once; there is no attaching of other people's
    await page.getByRole('tab', { name: 'MCP servers' }).click()
    await expect(field(page, 'Attach a server')).toHaveCount(0)
    await page.getByRole('button', { name: 'New MCP server' }).click()
    const mcp = unique('Calc')
    const create = dialog(page, 'New MCP server')
    await field(create, 'Name').getByRole('textbox').fill(mcp)
    await field(create, 'URL').getByRole('textbox').fill(`http://${unique('h').replace(/[^a-z0-9]/g, '')}:9100/mcp`)
    await create.getByRole('button', { name: 'Save' }).click()
    await expect(toast(page, 'MCP server created')).toBeVisible()
    await expect(row(page, mcp)).toBeVisible()

    // tokens: for its own agent, up to the user role
    await sidebar(page).getByRole('link', { name: 'Tokens', exact: true }).click()
    await expect(row(page, 'my user token')).toContainText('you')
    await page.getByRole('button', { name: 'New token' }).click()
    const dlg = dialog(page, 'New token')
    await expect(field(dlg, 'Agent').getByRole('combobox')).toHaveCount(0) // it can only name its own agent
    await field(dlg, 'Role').getByRole('combobox').click()
    await expect(page.getByRole('option').locator('.font-medium')).toHaveText(['regular', 'user']) // never admin or owner
    await page.getByRole('option', { name: 'regular' }).click()
    await field(dlg, 'Name').getByRole('textbox').fill('site token')
    await dlg.getByRole('button', { name: 'Create' }).click()
    // the secret is shown once
    const secret = dialog(page, 'Copy the token now')
    await expect(secret.getByTestId('new-token')).toHaveText(/^[A-Za-z0-9_]{64}$/)
    const shown = (await secret.getByTestId('new-token').innerText()).trim()
    const works = await request.get('/api/v1/tokens/self', { headers: { Authorization: `Bearer ${shown}` } })
    expect((await works.json()).name).toBe('site token')
    await closeSecret(page)
    await expect(row(page, 'site token')).toContainText('regular')
    // ... and the list never holds it
    await expect(page.getByText(shown)).toHaveCount(0)

    // the knowledge base, memories and users are its agent's, with no picker
    for (const path of ['/rag', '/memories', '/users']) {
      await page.goto(path)
      await expect(field(page, 'Agent')).toContainText(agent.name)
      await expect(field(page, 'Agent').getByRole('combobox')).toHaveCount(0)
    }
    await page.goto('/usage')
    await expect(page.getByRole('heading', { name: 'Usage' })).toBeVisible()
  } finally {
    await context.close()
    await dropAgent(request, agent.id)
    await dropAgent(request, other.id)
    const servers = await (await request.get('/api/v1/admin/mcp-servers', { headers: AUTH })).json()
    for (const s of servers.filter((x: { name: string }) => x.name.startsWith('Calc-'))) await request.delete(`/api/v1/admin/mcp-servers/${s.id}`, { headers: AUTH })
  }
})

test('admin: sees everything, hands out tokens up to user, and picks the agent to work as', async ({ browser, request }) => {
  const home = await newAgent(request, unique('Admin home'))
  const other = await newAgent(request, unique('Other agent'))
  const token = await newToken(request, home.id, 'admin', 'an admin token')
  const { page, context } = await signInAs(browser, token.token)
  const actAs: string[] = []
  page.on('request', (r) => {
    const h = r.headers()['x-act-as-agent']
    if (h && r.url().includes('/api/v1/users')) actAs.push(h)
  })
  try {
    await page.goto('/tokens')
    await expect(row(page, 'an admin token')).toBeVisible()
    await page.getByRole('button', { name: 'New token' }).click()
    const dlg = dialog(page, 'New token')
    await field(dlg, 'Role').getByRole('combobox').click()
    await expect(page.getByRole('option').locator('.font-medium')).toHaveText(['regular', 'user']) // an admin cannot hand out admin
    await page.keyboard.press('Escape')
    // it may name any agent
    await field(dlg, 'Agent').getByRole('combobox').click()
    await chooseCard(page, other.name)
    await field(dlg, 'Name').getByRole('textbox').fill('for the other agent')
    await dlg.getByRole('button', { name: 'Create' }).click()
    await closeSecret(page)
    await expect(row(page, 'for the other agent')).toContainText(other.name)
    // the token of an owner is not its to touch
    const ownerRow = row(page, 'initial')
    await expect(ownerRow.getByRole('button', { name: 'Delete' })).toBeDisabled()
    await expect(ownerRow.getByRole('button', { name: 'Edit' })).toBeDisabled()

    // Users: it starts on its own agent and may work as another (X-Act-As-Agent)
    await page.goto('/users')
    await expect(field(page, 'Agent').getByRole('combobox')).toContainText(home.name)
    await field(page, 'Agent').getByRole('combobox').click()
    await chooseCard(page, other.name)
    await expect(page).toHaveURL(new RegExp(`agent=${other.id}`))
    await field(page, 'External id').getByRole('combobox').fill('abc')
    await expect(page.getByText(/No users start with/)).toBeVisible()
    expect(actAs).toContain(String(other.id))
    await page.keyboard.press('Escape') // close the suggestions, so the page behind is reachable again

    for (const item of ['Agents', 'Models', 'MCP servers', 'Metrics', 'Usage']) await expect(sidebar(page).getByRole('link', { name: item, exact: true })).toBeVisible()
  } finally {
    await context.close()
    await dropAgent(request, home.id)
    await dropAgent(request, other.id)
  }
})

test('owner: may hand out every role', async ({ browser, request }) => {
  const agent = await newAgent(request)
  const token = await newToken(request, agent.id, 'owner', 'a second owner')
  const { page, context } = await signInAs(browser, token.token)
  try {
    await page.goto('/tokens')
    await page.getByRole('button', { name: 'New token' }).click()
    await field(dialog(page, 'New token'), 'Role').getByRole('combobox').click()
    await expect(page.getByRole('option').locator('.font-medium')).toHaveText(['regular', 'user', 'admin', 'owner'])
    await page.keyboard.press('Escape')
    await dialog(page, 'New token').getByRole('button', { name: 'Cancel' }).click()
    // it does not delete the initial token, nor itself
    await expect(row(page, 'initial').getByRole('button', { name: 'Delete' })).toBeDisabled()
    await expect(row(page, 'a second owner').getByRole('button', { name: 'Delete' })).toBeDisabled()
  } finally {
    await context.close()
    await dropAgent(request, agent.id)
  }
})

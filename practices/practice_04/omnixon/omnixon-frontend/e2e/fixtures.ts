import { expect, test as base, type APIRequestContext, type Browser, type Locator, type Page } from '@playwright/test'

export const TOKEN = process.env.OMNIXON_TOKEN ?? 'e2e-admin-token'

/** Every test starts signed in (the sign-in flow itself is covered in auth.spec.ts). */
export const test = base.extend({
  page: async ({ page }, provide) => {
    await page.addInitScript((token) => localStorage.setItem('omnixon.token', token), TOKEN)
    await provide(page)
  },
})
export { expect }

/** A name that does not collide with data from other tests or earlier runs. */
export const unique = (prefix: string) => `${prefix}-${Date.now().toString(36)}${Math.floor(Math.random() * 1e3)}`

/** A form field by its label (Field renders role=group labelled by its label). */
export const field = (scope: Page | Locator, label: string) => scope.getByRole('group', { name: label, exact: true })

export const dialog = (page: Page, name?: string | RegExp) => page.getByRole('dialog', name ? { name } : undefined)

/** The Name box of a form. */
export const nameBox = (scope: Page | Locator) => field(scope, 'Name').getByRole('textbox')

/** Signs in with a token in a fresh browser context (no stored token); close the context when done. */
export async function signInAs(browser: Browser, token: string) {
  const context = await browser.newContext()
  const page = await context.newPage()
  // every call to /admin the panel makes from now on (a regular token must make none)
  const adminCalls: string[] = []
  page.on('request', (r) => r.url().includes('/api/v1/admin/') && adminCalls.push(`${r.method()} ${r.url()}`))
  await page.goto('/login')
  await page.getByPlaceholder('Your token').fill(token)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: /^(Dashboard|Playground)$/ })).toBeVisible() // the first page depends on the role
  return { page, context, adminCalls }
}

export const AUTH = { Authorization: `Bearer ${TOKEN}` }

/** A card in an open picker, by the id badge on it. */
export const optionWithId = (page: Page, id: string | number) =>
  page.getByRole('option').filter({ has: page.locator('span.value-mono', { hasText: new RegExp(`^${id}$`) }) })

export const row = (page: Page | Locator, text: string | RegExp) => page.getByRole('row').filter({ hasText: text })

/** Toasts (sonner) are announced in a list; wait for one with this text. */
export const toast = (page: Page, text: string | RegExp) => page.locator('[data-sonner-toast]').filter({ hasText: text }).first()

type Api = import('@playwright/test').APIRequestContext
export type Role = 'regular' | 'user' | 'admin' | 'owner'
export interface MadeToken {
  id: number
  name: string
  role: Role
  agent_id: number
  token: string
}

/** An agent of its own (so tokens made for it work as that agent). */
export async function newAgent(request: Api, name = unique('Agent'), extra: Record<string, unknown> = {}) {
  const res = await request.post('/api/v1/admin/agents', { headers: AUTH, data: { name, prompt: '', model_id: 0, ...extra } })
  expect(res.status()).toBe(201)
  return (await res.json()) as { id: number; name: string }
}

export async function newToken(request: Api, agentId: number, role: Role, name = unique(`${role} token`)): Promise<MadeToken> {
  const res = await request.post('/api/v1/admin/tokens', { headers: AUTH, data: { name, role, agent_id: agentId } })
  expect(res.status()).toBe(201)
  return (await res.json()) as MadeToken
}

/** Removes an agent and every token on it. */
export async function dropAgent(request: Api, agentId: number) {
  const tokens = await (await request.get('/api/v1/admin/tokens', { headers: AUTH, params: { agent_id: agentId } })).json()
  for (const t of tokens) await request.delete(`/api/v1/admin/tokens/${t.id}`, { headers: AUTH })
  await request.delete(`/api/v1/admin/agents/${agentId}`, { headers: AUTH })
}

/** Picks a card of an open picker by clicking its name (the middle of a card may be a link to a related entity). */
export const chooseCard = (page: Page, name: string | RegExp) => page.getByRole('option').filter({ hasText: name }).locator('.font-medium').first().click()

/** Closes the dialog that shows a new token's secret (its footer button; the corner cross has the same name). */
export const closeSecret = (page: Page) => dialog(page, 'Copy the token now').locator('[data-slot=dialog-footer]').getByRole('button', { name: 'Close' }).click()

/** The sidebar. */
export const sidebar = (page: Page) => page.locator('[data-sidebar=sidebar]')

/** An agent with a `user` token on a model of the fake OpenAI-compatible server of the stack (docker/fake-llm): `fake/pong*` answers
 *  "pong", `fake/slow*` says 40 words a quarter of a second apart (an answer that takes ten seconds). `drop()` removes all three. */
export async function fakeAgent(request: APIRequestContext, modelPrefix: string, role: 'regular' | 'user' = 'user') {
  const post = async (path: string, body: object) => {
    const res = await request.post(`/api/v1/admin/${path}`, { headers: AUTH, data: body })
    expect(res.status(), await res.text()).toBe(201)
    return res.json()
  }
  const model = await post('models', { name: unique('Slow'), request_json: { model: unique(modelPrefix) }, base_url: 'http://fake-llm:8000/v1' })
  const agent = await post('agents', { name: unique('Slow agent'), prompt: '', model_id: model.id, config: { tools: [], auto_memory: false } })
  const token = await post('tokens', { name: unique('slow token'), role, agent_id: agent.id })
  return {
    token: token.token as string,
    agentId: agent.id as number,
    async drop() {
      await request.delete(`/api/v1/admin/tokens/${token.id}`, { headers: AUTH })
      await request.delete(`/api/v1/admin/agents/${agent.id}`, { headers: AUTH })
      await request.delete(`/api/v1/admin/models/${model.id}`, { headers: AUTH })
    },
  }
}


/** The Playground keeps its settings (agent, user, answer mode, flags) in a dialog. */
export async function openSettings(page: Page) {
  await page.getByRole('button', { name: 'Change settings' }).click()
  const settings = dialog(page, 'Playground settings')
  await expect(settings).toBeVisible()
  return settings
}

export async function closeSettings(page: Page) {
  // (a click on the title first: it closes the list of suggestions, which hides the dialog from the page while it is open)
  await page.locator('[data-slot=dialog-title]').filter({ hasText: 'Playground settings' }).click()
  await page.locator('[data-slot=dialog-footer]').getByRole('button', { name: 'Close' }).click()
  await expect(dialog(page, 'Playground settings')).toHaveCount(0)
}

/** Switches the Playground to a single response (one JSON answer instead of a stream). */
export async function singleResponse(page: Page) {
  const settings = await openSettings(page)
  await settings.getByRole('button', { name: 'Single response' }).click()
  await closeSettings(page)
}

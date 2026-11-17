import type { Page } from '@playwright/test'
import { AUTH, dropAgent, expect, newAgent, newToken, row, test, unique } from './fixtures'

test('a request is counted on its token and the statistics show it, with charts', async ({ page, request }) => {
  const agent = await newAgent(request, unique('Counted agent'))
  const token = await newToken(request, agent.id, 'regular', 'counted token')
  try {
    // the model call fails in the test stack (no key): it is still counted, as a failed request, with nothing spent
    const res = await request.post('/api/v1/request', { headers: { Authorization: `Bearer ${token.token}` }, data: { request: 'zebra-marker-1', user_id: 'usage_e2e' } })
    expect(res.status()).toBe(502)

    await page.goto('/usage')
    await expect(page.getByRole('heading', { name: 'Usage' })).toBeVisible()
    // the token is among the tokens, with its one failed request
    const byToken = page.getByRole('region', { name: 'Usage by token' })
    await expect(row(byToken, 'counted token')).toBeVisible()
    await expect(row(byToken, 'counted token').getByRole('cell').nth(1)).toHaveText('1') // requests
    await expect(row(byToken, 'counted token').getByRole('cell').nth(2)).toHaveText('1') // failed
    // the charts are drawn
    for (const id of ['chart-requests', 'chart-tokens', 'chart-cost']) await expect(page.getByTestId(id).locator('svg.recharts-surface').first()).toBeVisible()
    // nothing of what was said is anywhere on the page
    expect(await page.content()).not.toContain('zebra-marker-1')

    // narrowed to the token
    await page.getByRole('group', { name: 'Token', exact: true }).getByRole('combobox').click()
    await page.getByRole('option').filter({ hasText: 'counted token' }).click()
    await expect(page.getByTestId('kpi-requests')).toHaveText('1')
    await expect(page.getByTestId('kpi-failed')).toHaveText('1')
  } finally {
    await dropAgent(request, agent.id)
  }
})

async function mockUsage(page: Page) {
  const day = new Date().toLocaleDateString('en-CA')
  const row = (token: string, model: string, n: number, cost: number) => ({
    day, token_id: 1, token_name: token, model, requests: n, errors: 1, input_tokens: 1000 * n, output_tokens: 500 * n, cost, duration_ms_sum: 2000 * n,
  })
  await page.route('**/api/v1/admin/usage?*', (route) =>
    route.fulfill({ json: [row('bot one', 'a/model-1', 10, 0.5), row('bot two', 'b/model-2', 4, 0.25)] }),
  )
  await page.route('**/api/v1/admin/usage/monthly*', (route) =>
    route.fulfill({
      json: [
        { month: '2026-07-01', token_id: null, token_name: 'old bot', model: 'a/model-1', requests: 100, errors: 2, input_tokens: 90000, output_tokens: 40000, cost: 3.5, duration_ms_sum: 90000 },
        { month: '2026-08-01', token_id: 1, token_name: 'bot one', model: 'a/model-1', requests: 50, errors: 0, input_tokens: 40000, output_tokens: 20000, cost: 1.25, duration_ms_sum: 40000 },
      ],
    }),
  )
}

test('the numbers add up: totals, tables by token and by model, and the folded months', async ({ page }) => {
  await mockUsage(page)
  await page.goto('/usage')
  await expect(page.getByTestId('kpi-requests')).toHaveText('14')
  await expect(page.getByTestId('kpi-failed')).toHaveText('2')
  await expect(page.getByTestId('kpi-cost')).toHaveText('$0.75')
  await expect(page.getByTestId('kpi-tokens')).toContainText('21K') // 14 000 in + 7 000 out
  await expect(page.getByTestId('kpi-average-time')).toContainText('2.0 s')

  const byToken = page.getByRole('region', { name: 'Usage by token' })
  await expect(row(byToken, 'bot one')).toContainText('$0.50')
  await expect(row(byToken, 'bot two')).toContainText('$0.25')
  const byModel = page.getByRole('region', { name: 'Usage by model' })
  await expect(row(byModel, 'a/model-1')).toBeVisible()
  await expect(row(byModel, 'b/model-2')).toBeVisible()

  // earlier months, folded, including a deleted token's
  await expect(page.getByTestId('chart-months').locator('svg.recharts-surface').first()).toBeVisible()
  await expect(page.getByTestId('chart-models').locator('svg.recharts-surface').first()).toBeVisible()
})

test('an empty period says so instead of drawing nothing', async ({ page }) => {
  await page.route('**/api/v1/admin/usage?*', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/v1/admin/usage/monthly*', (route) => route.fulfill({ json: [] }))
  await page.goto('/usage')
  await expect(page.getByTestId('kpi-requests')).toHaveText('0')
  // each chart says why it is empty instead of drawing bare axes
  await expect(page.getByText('No requests in this period')).toHaveCount(4) // the three charts and the share by model
  await expect(page.getByTestId('chart-requests')).toHaveCount(0)
  await expect(page.getByTestId('months-empty')).toContainText('No earlier months yet')
  await expect(page.getByTestId('months-empty')).toContainText('folded')
  await expect(page.getByText('No usage yet').first()).toBeVisible()
})

test('a request made while acting as another agent is counted on the token of the one who acted', async ({ page, request }) => {
  const agent = await newAgent(request, unique('Acted-as agent'))
  try {
    const mine = await (await request.get('/api/v1/tokens/self', { headers: AUTH })).json()
    await request.post('/api/v1/request', { headers: { ...AUTH, 'X-Act-As-Agent': String(agent.id) }, data: { request: 'hi', user_id: 'acted_e2e' } })
    const rows = await (await request.get('/api/v1/admin/usage', { headers: AUTH, params: { token_id: mine.id } })).json()
    expect(rows.reduce((n: number, r: { requests: number }) => n + r.requests, 0)).toBeGreaterThanOrEqual(1)
    await page.goto('/usage')
    await expect(row(page.getByRole('region', { name: 'Usage by token' }), 'initial')).toBeVisible()
  } finally {
    await dropAgent(request, agent.id)
  }
})

test('a month without usage between two that had some is shown as quiet, not left out', async ({ page }) => {
  await page.route('**/api/v1/admin/usage?*', (route) => route.fulfill({ json: [] }))
  const month = (m: string, requests: number, cost: number) => ({ month: m, token_id: 1, token_name: 'bot', model: 'a/b', requests, errors: 0, input_tokens: 10, output_tokens: 5, cost, duration_ms_sum: 100 })
  await page.route('**/api/v1/admin/usage/monthly*', (route) => route.fulfill({ json: [month('2026-06-01', 7, 0.7), month('2026-09-01', 3, 0.3)] }))
  await page.goto('/usage')
  const months = page.getByRole('list', { name: 'Months' })
  await expect(months.getByRole('listitem')).toHaveCount(4) // June, July, August, September
  await expect(months.getByRole('listitem').filter({ hasText: '2026-07' })).toContainText('No usage')
  await expect(months.getByRole('listitem').filter({ hasText: '2026-08' })).toContainText('No usage')
  await expect(months.getByRole('listitem').filter({ hasText: '2026-06' })).toContainText('7 requests')
  await expect(page.getByTestId('chart-months').locator('svg.recharts-surface').first()).toBeVisible()
})

test('each table row is one line, the two tables sit side by side only when both fit, and the last card is not cut off', async ({ page }) => {
  const day = new Date().toLocaleDateString('en-CA')
  const entry = (t: string, m: string, n: number) => ({ day, token_id: 1, token_name: t, model: m, requests: n, errors: 1, input_tokens: 1000 * n, output_tokens: 500 * n, cost: 0.1 * n, duration_ms_sum: 2000 * n })
  await page.route('**/api/v1/admin/usage?*', (route) => route.fulfill({ json: [entry('a rather long token name', 'openai/gpt-4o-mini-2024', 10), entry('bot two', 'b/model-2', 4)] }))
  await page.route('**/api/v1/admin/usage/monthly*', (route) => route.fulfill({ json: [] }))

  for (const [width, sideBySide] of [[1440, false], [2600, true]] as const) {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/usage')
    const byToken = page.getByRole('region', { name: 'Usage by token' })
    const byModel = page.getByRole('region', { name: 'Usage by model' })
    await expect(row(byToken, 'bot two')).toBeVisible()
    const [a, b] = [(await byToken.boundingBox())!, (await byModel.boundingBox())!]
    if (sideBySide) expect(Math.abs(a.y - b.y), `at ${width}px side by side`).toBeLessThan(4)
    else expect(b.y, `at ${width}px one under the other`).toBeGreaterThan(a.y + a.height - 4)
    // whichever way they sit, a row is one line, with nothing cut off on its right
    for (const table of [byToken, byModel]) {
      for (const r of await table.getByRole('row').all()) {
        const h = (await r.boundingBox())!.height
        expect(h, 'a row is one line').toBeLessThan(60)
      }
      const t = (await table.getByRole('table').boundingBox())!
      expect(t.width).toBeGreaterThan(300)
    }
  }

  // the card at the bottom is reachable and whole (it used to be squeezed to its title)
  await page.setViewportSize({ width: 1440, height: 800 })
  await page.goto('/usage')
  const card = page.locator('[data-slot=card]').filter({ hasText: 'Earlier months' })
  await card.scrollIntoViewIfNeeded()
  await expect(page.getByTestId('months-empty')).toBeInViewport()
  const box = (await card.boundingBox())!
  expect(box.height).toBeGreaterThan(150)
})

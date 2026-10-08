import { expect, test } from './fixtures'

test('dashboard shows a healthy, migrated service and this token', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  await expect(page.getByText(/database migrated to \d+/)).toBeVisible()
  await expect(page.getByRole('main').getByText('owner, initial', { exact: true })).toBeVisible()
  await expect(page.getByRole('main').getByText('Default agent')).toBeVisible() // the agent of the token, by name
  await expect(page.getByText('No prompt')).toBeVisible() // the agent of the initial token starts with an empty prompt
})

test('metrics page lists service metrics, and /metrics is the panel, not Prometheus text', async ({ page }) => {
  await page.goto('/metrics')
  await expect(page.getByRole('heading', { name: 'Metrics' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'omnixon_http_requests_total' }).first()).toBeVisible()
  await page.getByRole('tab', { name: 'Raw' }).click()
  await expect(page.getByText('# TYPE omnixon_http_requests_total counter')).toBeVisible()
})

test('the dashboard has cards that lead to every part of the panel', async ({ page }) => {
  await page.goto('/')
  for (const [title, url] of [
    ['Playground', '/chat'],
    ['Agents', '/agents'],
    ['Models', '/models'],
    ['MCP servers', '/mcp-servers'],
    ['Knowledge base', '/rag'],
    ['Memories', '/memories'],
    ['Users & history', '/users'],
    ['Tokens', '/tokens'],
    ['Usage', '/usage'],
    ['Metrics', '/metrics'],
  ]) {
    // the cards come after the four counters, which link to the same pages
    await expect(page.getByRole('main').getByRole('link', { name: new RegExp(`^${title}`) }).last()).toHaveAttribute('href', url)
  }
  await page.getByRole('main').getByRole('link', { name: /^Models/ }).last().click()
  await expect(page).toHaveURL(/\/models$/)
})

test('a long table scrolls inside the page and keeps its pager in view', async ({ page }) => {
  await page.goto('/metrics')
  await expect(page.getByRole('cell', { name: 'omnixon_http_requests_total' }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Next page' })).toBeInViewport()
  const scrolls = await page.evaluate(() => document.documentElement.scrollHeight > window.innerHeight + 1)
  expect(scrolls).toBe(false) // the page itself does not scroll
})

test('the border of a card is not cut off at the edge of the page', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  const card = page.locator('[data-slot=card]').first()
  await expect(card).toBeVisible()
  // the ring is a 1px shadow outside the card: its box and the box of the scrolling body must leave room for it
  const room = await card.evaluate((el) => {
    let scroller: HTMLElement | null = el.parentElement
    while (scroller && getComputedStyle(scroller).overflowY === 'visible') scroller = scroller.parentElement
    const c = el.getBoundingClientRect()
    const s = scroller!.getBoundingClientRect()
    const pad = parseFloat(getComputedStyle(scroller!).paddingLeft)
    return { left: c.left - s.left, top: c.top - s.top, pad }
  })
  expect(room.left).toBeGreaterThanOrEqual(1)
  expect(room.top).toBeGreaterThanOrEqual(1)
})

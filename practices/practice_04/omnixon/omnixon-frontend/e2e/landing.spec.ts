import { expect, test as base } from '@playwright/test'

// The front page, for somebody who is not signed in.
const test = base

test('the front page presents Omnixon and puts the login at the top left', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Omnixon', level: 1 })).toBeAttached() // the wordmark is drawn on a canvas; the heading is for readers
  await expect(page.locator('canvas').first()).toBeVisible()

  // the way in is the first thing in the header, left of the name
  const login = page.getByRole('banner').locator('a[href="/login"]').first()
  const name = page.getByRole('banner').getByRole('link', { name: 'Omnixon' })
  await expect(login).toBeVisible()
  const [a, b] = [await login.boundingBox(), await name.boundingBox()]
  expect(a!.x).toBeLessThan(b!.x)
  expect(a!.x).toBeLessThan(200)

  // what it can do, in English
  await expect(page.getByRole('heading', { name: 'One chat API' })).toBeVisible()
  for (const feature of ['Memory that lasts', 'A knowledge base per agent', 'MCP tools', 'Versions and rollback', 'Files and voice', 'Tokens with roles', 'Usage per token']) {
    await expect(page.getByRole('heading', { name: feature })).toBeAttached()
  }
  await expect(page.getByText('From nothing to answers in three steps')).toBeAttached()
})

test('Login on the front page leads to the sign in', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('banner').locator('a[href="/login"]').first().click()
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  await page.getByRole('link', { name: 'About Omnixon' }).click()
  await expect(page).toHaveURL(/\/$/)
})

test('the front page works on a phone and in both themes', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 })
  await page.goto('/')
  await expect(page.getByRole('banner').locator('a[href="/login"]').first()).toBeVisible()
  const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
  expect(wide).toBe(false) // no sideways scroll
  await page.getByRole('button', { name: 'Toggle theme' }).click()
  await expect(page.getByRole('banner').locator('a[href="/login"]').first()).toBeVisible()
})

test('the code on the front page is coloured, with the Python and curl examples in tabs', async ({ page }) => {
  await page.goto('/')
  const code = page.locator('#code')
  await code.scrollIntoViewIfNeeded()
  const python = code.locator('[data-slot=code-block]')
  await expect(python.locator('pre.shiki')).toBeVisible()
  const colours = await python.locator('pre.shiki span').evaluateAll((els) => new Set(els.map((el) => getComputedStyle(el).color)).size)
  expect(colours).toBeGreaterThanOrEqual(4) // keywords, strings, functions, plain text: not all one white
  await code.getByRole('tab', { name: 'curl' }).click()
  await expect(code.locator('[data-slot=code-block]')).toContainText('Authorization: Bearer')
  await expect(code.locator('[data-slot=code-block] pre.shiki')).toBeVisible()
})

test('the top of the front page is not overloaded: the name, a tagline and a request with its answer', async ({ page }) => {
  await page.goto('/')
  // no badge, no second row of buttons, no pills: the sign in is in the header
  await expect(page.getByText('One API for every model, memory and tool', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('list', { name: 'What it does' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'See what it does' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Sign in' })).toHaveCount(0)
  await expect(page.getByRole('banner').locator('a[href="/login"]').first()).toBeVisible() // the way in stays in the header
  // next to the request is the JSON that comes back: the answer in full and nothing else but dots
  const answer = page.getByTestId('hero-chat')
  await expect(answer).toContainText('"response"')
  await expect(answer).toContainText('You said the team plan stays at $20 a seat, and the free tier gets 100 requests a month. I also remember you prefer yearly billing.')
  await expect(answer).not.toContainText('"user"') // the other fields are not worth naming: just a dots line
  await expect(answer).not.toContainText('"trace"')
  await expect(answer.locator('pre')).toHaveText(/\n\s*\.\.\.\s*\n\}$/)
  await expect(answer).not.toContainText('214 tokens') // no made-up statistics
  await expect(answer.locator('pre.shiki')).toBeVisible()
  // the address in the examples is the real one, and the footer links to it
  await expect(page.getByLabel('A request and its answer')).toContainText('curl https://omnixon.net/api/v1/request')
  await expect(page.getByRole('contentinfo').getByRole('link', { name: 'omnixon.net' })).toHaveAttribute('href', 'https://omnixon.net')
  // the request next to it is real code, coloured
  await expect(page.getByLabel('A request and its answer').locator('pre.shiki').first()).toBeVisible()
})

test('the top of the front page fills the screen, with the name in the middle of the room above the example', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/')
  const hero = page.locator('main > div > section').first()
  const header = (await page.getByRole('banner').boundingBox())!
  const box = (await hero.boundingBox())!
  // the strip of what it is built with is under the hero and ends at the bottom of the screen: it is in the frame
  const strip = (await page.getByLabel('Built with').first().boundingBox())!
  expect(strip.y).toBeGreaterThanOrEqual(box.y + box.height - 1)
  expect(strip.y + strip.height).toBeGreaterThanOrEqual(900 - 1)
  expect(strip.y + strip.height).toBeLessThanOrEqual(900 + 1)
  expect(box.y).toBeLessThanOrEqual(header.y + header.height + 1)
  // equal room above and below the name: between the header and the name, and between the tagline and the example
  const name = (await page.locator('main section').first().locator('h1 + div > div[aria-hidden]').first().boundingBox())!
  const tagline = (await page.locator('main section').first().locator('p').first().boundingBox())!
  const example = (await page.getByLabel('A request and its answer').boundingBox())!
  const above = name.y - (header.y + header.height)
  const below = example.y - (tagline.y + tagline.height)
  expect(Math.abs(above - below)).toBeLessThanOrEqual(24)
})

test('the mark is an O, as the first letter of the name', async ({ page, request }) => {
  const svg = await (await request.get('/favicon.svg')).text()
  expect(svg).toContain('<circle')
  expect(svg).not.toContain('<path') // no longer the U
  await page.goto('/')
  await expect(page.getByRole('banner').getByRole('img', { name: 'Omnixon' })).toBeVisible()
})

test('the front page ends with a graph of channels, agents and models around Omnixon', async ({ page }) => {
  await page.goto('/')
  const section = page.getByRole('region', { name: 'Channels, agents and models' })
  await section.scrollIntoViewIfNeeded()
  const graph = section.locator('[role=img][aria-label^="Channels such as"]')
  await expect(graph).toBeVisible()
  for (const node of ['telegram', 'whatsapp', 'discord', 'avito', 'site', 'omnixon', 'support', 'sales', 'docs', 'booking', 'gpt', 'claude', 'gemini', 'local']) {
    await expect(graph.locator(`[data-node="${node}"]`), node).toBeVisible()
  }
  await expect(graph.locator('[data-node=telegram]')).toContainText('Telegram')
  await expect(graph.locator('[data-node=whatsapp]')).toContainText('WhatsApp')
  // every channel is joined to Omnixon, Omnixon to every agent, and each agent to the models it runs on
  expect(await graph.locator('path[data-edge$="-hub"]').count()).toBe(6)
  expect(await graph.locator('path[data-edge^="hub-"]').count()).toBe(4)
  // an agent runs on one model and a model serves one agent: four lines between the last two columns, no two from one card
  const runs = await graph.locator('path[data-edge]:not([data-edge$="-hub"]):not([data-edge^="hub-"])').evaluateAll((els) => els.map((e) => e.getAttribute('data-edge')!))
  expect(runs).toHaveLength(4)
  expect(new Set(runs.map((r) => r.split('-')[0])).size).toBe(4)
  expect(new Set(runs.map((r) => r.split('-')[1])).size).toBe(4)
  expect(await graph.locator('path[data-edge]').count()).toBe(6 + 4 + 4)
  // the messengers wear their brand colours, and nothing else in the figure is coloured
  const brands = await graph.locator('[data-brand]').evaluateAll((els) => els.map((e) => [e.closest('[data-node]')!.getAttribute('data-node'), e.getAttribute('data-brand')]))
  expect(Object.fromEntries(brands)).toEqual({ telegram: '#229ED9', whatsapp: '#25D366', discord: '#5865F2', avito: '#0099F7', vk: '#0077FF' })
  await expect(graph.locator('[data-node=site] [data-brand]')).toHaveCount(0)
  await expect(graph.locator('[data-node=omnixon] [data-brand], [data-node=support] [data-brand], [data-node=gpt] [data-brand]')).toHaveCount(0)
  // the figure sits above the closing call to action
  const box = (await section.boundingBox())!
  const cta = (await page.getByRole('heading', { name: 'Ready to see it work?' }).boundingBox())!
  expect(box.y + box.height).toBeLessThanOrEqual(cta.y)
  // and the cards do not overlap each other
  const boxes = await graph.locator('[data-node]').evaluateAll((els) => els.map((e) => e.getBoundingClientRect()).map((r) => [r.left, r.top, r.right, r.bottom]))
  for (let i = 0; i < boxes.length; i++)
    for (let j = i + 1; j < boxes.length; j++) {
      const [a, b] = [boxes[i], boxes[j]]
      expect(a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3], `cards ${i} and ${j} overlap`).toBe(false)
    }
})

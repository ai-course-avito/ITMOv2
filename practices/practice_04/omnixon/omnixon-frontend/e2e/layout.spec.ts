import { AUTH, dialog, dropAgent, expect, field, newAgent, row, test, unique } from './fixtures'

// Sizes that were wrong once: the list of cards in a picker, the room above a form's buttons, the sidebar.

const FIVE = 5

async function expectFiveWholeCards(page: import('@playwright/test').Page) {
  const list = page.locator('[data-slot=combobox-list]')
  await expect(list).toBeVisible()
  const cards = list.getByRole('option')
  await expect(cards.nth(FIVE)).toBeAttached() // more than five, so it has to scroll
  // let the popup finish opening (it zooms in) before measuring
  await list.evaluate((el) =>
    Promise.all(
      el
        .closest('[data-slot=combobox-content]')!
        .getAnimations({ subtree: true })
        .map((a) => a.finished),
    ),
  )
  const box = (await list.boundingBox())!
  const heights = new Set<number>()
  for (let i = 0; i < FIVE; i++) {
    const c = (await cards.nth(i).boundingBox())!
    heights.add(Math.round(c.height))
    expect(c.y, `card ${i + 1} starts inside the list`).toBeGreaterThanOrEqual(box.y - 0.5)
    expect(c.y + c.height, `card ${i + 1} ends inside the list (not cropped)`).toBeLessThanOrEqual(
      box.y + box.height + 0.5,
    )
  }
  expect(heights.size, 'every card is as tall as the others').toBe(1)
  // it still scrolls, and the sixth card is not fully in view before that
  const sixth = (await cards.nth(FIVE).boundingBox())!
  expect(sixth.y + sixth.height).toBeGreaterThan(box.y + box.height + 0.5)
  expect(await list.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true)
  await list.evaluate((el) => (el.scrollTop = el.scrollHeight))
  await expect(cards.last()).toBeInViewport()
}

test('a picker of cards shows five whole cards (each with up to three rows) and scrolls beyond them', async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 1280, height: 1300 })
  const made: number[] = []
  for (let i = 0; i < 6; i++) {
    const a = await (
      await request.post('/api/v1/admin/agents', {
        headers: AUTH,
        data: { name: unique(`Card ${i}`), prompt: `Prompt number ${i} of the list`, model_id: 0 },
      })
    ).json()
    made.push(a.id)
  }
  try {
    // an entity picker (agents) in a dialog
    await page.goto('/tokens')
    await page.getByRole('button', { name: 'New token' }).click()
    await field(dialog(page, 'New token'), 'Agent').getByRole('combobox').click()
    await expectFiveWholeCards(page)
    await page.keyboard.press('Escape')
    await page.keyboard.press('Escape')

    // an entity picker on a page (the agent of the knowledge base)
    await page.goto('/rag')
    await field(page, 'Agent').getByRole('combobox').click()
    await expectFiveWholeCards(page)
  } finally {
    for (const id of made) await request.delete(`/api/v1/admin/agents/${id}`, { headers: AUTH })
  }
})

test('the suggestions of users are cards of the same size', async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 1300 })
  const prefix = unique('sz').replace(/[^a-z0-9]/g, '')
  const ids = Array.from({ length: 6 }, (_, i) => `${prefix}-${i}`)
  for (const external_id of ids) await request.post('/api/v1/users', { headers: AUTH, data: { external_id } })
  try {
    await page.goto('/users')
    await field(page, 'External id').getByRole('combobox').fill(prefix)
    await expectFiveWholeCards(page)
  } finally {
    for (const id of ids) await request.delete(`/api/v1/users/${id}`, { headers: AUTH })
  }
})

test('the list of cards fits a short window and still scrolls', async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 560 })
  const made: number[] = []
  for (let i = 0; i < 6; i++) {
    const a = await (
      await request.post('/api/v1/admin/agents', {
        headers: AUTH,
        data: { name: unique(`Short ${i}`), prompt: '', model_id: 0 },
      })
    ).json()
    made.push(a.id)
  }
  try {
    await page.goto('/rag')
    await field(page, 'Agent').getByRole('combobox').click()
    const list = page.locator('[data-slot=combobox-list]')
    await expect(list).toBeVisible()
    const box = (await list.boundingBox())!
    expect(box.y + box.height).toBeLessThanOrEqual(560) // inside the window
    expect(await list.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true)
  } finally {
    for (const id of made) await request.delete(`/api/v1/admin/agents/${id}`, { headers: AUTH })
  }
})

test('there is room between the last field of a form and its buttons', async ({ page }) => {
  for (const [open, title] of [
    [() => page.getByRole('button', { name: 'New token' }).click(), 'New token'],
    [() => page.getByRole('button', { name: 'New model' }).click(), 'New model'],
  ] as const) {
    await page.goto(title === 'New token' ? '/tokens' : '/models')
    await open()
    const card = dialog(page, title)
    await expect(card.getByRole('button', { name: 'Cancel' })).toBeVisible()
    await card.evaluate((el) => Promise.all(el.getAnimations({ subtree: true }).map((a) => a.finished)))
    // scroll to the bottom so that the last field is the one next to the buttons
    await card
      .locator('[data-slot=dialog-footer]')
      .evaluate((f) => (f.previousElementSibling as HTMLElement | null)?.scrollTo(0, 1e6))
    const last = (await card.locator('[data-slot=field], [data-slot=collapsible-trigger]').last().boundingBox())!
    const footer = (await card.locator('[data-slot=dialog-footer]').boundingBox())!
    const gap = footer.y - (last.y + last.height)
    expect(gap, `${title}: room above the buttons`).toBeGreaterThanOrEqual(20)
    expect(gap, `${title}: not a huge gap`).toBeLessThanOrEqual(64)
    await card.getByRole('button', { name: 'Cancel' }).click()
  }
})

test('the sidebar items are spaced out, with a clear active item', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/models')
  const nav = page.locator('[data-sidebar=sidebar]')
  const a = (await nav.getByRole('link', { name: 'Agents', exact: true }).boundingBox())!
  const m = (await nav.getByRole('link', { name: 'Models', exact: true }).boundingBox())!
  expect(m.y - (a.y + a.height), 'gap between two items').toBeGreaterThanOrEqual(5)
  expect(a.height, 'item height').toBeGreaterThanOrEqual(34)
  // the whole menu still fits a normal window without scrolling its own content
  const content = nav.locator('[data-sidebar=content]')
  expect(await content.evaluate((el) => el.scrollHeight <= el.clientHeight + 1)).toBe(true)
  // the current page is the active item, no other one is
  await expect(nav.getByRole('link', { name: 'Models', exact: true })).toHaveAttribute('data-active')
  await expect(nav.locator('[data-sidebar=menu-button][data-active]')).toHaveCount(1)
  await page.goto('/agents/1')
  await expect(nav.getByRole('link', { name: 'Agents', exact: true })).toHaveAttribute('data-active') // a nested page keeps its parent active
})

test('the choices of a role are simple cards with room between them, each with its own icon', async ({ page }) => {
  await page.goto('/tokens')
  await page.getByRole('button', { name: 'New token' }).click()
  await page.getByRole('group', { name: 'Role', exact: true }).getByRole('combobox').click()
  const cards = page.getByRole('option')
  await expect(cards).toHaveCount(4) // an owner: every role
  await expect(cards.locator('svg').first()).toBeVisible()
  const boxes = []
  for (let i = 0; i < 4; i++) boxes.push((await cards.nth(i).boundingBox())!)
  for (let i = 1; i < 4; i++)
    expect(boxes[i].y - (boxes[i - 1].y + boxes[i - 1].height), `gap above card ${i + 1}`).toBeGreaterThanOrEqual(3.5)
  for (const card of [0, 1, 2, 3]) expect(boxes[card].height).toBeGreaterThanOrEqual(48) // a name and what it means, not a bare line
  // every role has a different icon
  const icons = await cards.evaluateAll((els) => els.map((el) => el.querySelector('svg')?.getAttribute('class') ?? ''))
  expect(new Set(icons).size).toBe(4)
})

test('the panel has no gradients: the brand and the dashboard are flat', async ({ page }) => {
  await page.goto('/')
  const gradients = await page
    .locator('[data-sidebar=sidebar] *, main *')
    .evaluateAll((els) => els.filter((el) => /gradient/.test(getComputedStyle(el).backgroundImage)).length)
  expect(gradients).toBe(0)
})

// A long prompt ran over the Model column: the cell had a capped width while the text could not wrap
test('long prompts and model settings are cut to 40 characters and stay in their column', async ({ page, request }) => {
  const name = unique('Long prompt')
  const agent = await newAgent(request, name, { prompt: 'You are a very patient assistant. '.repeat(8) })
  const modelName = unique('Long settings')
  const made = await request.post('/api/v1/admin/models', {
    headers: AUTH,
    data: {
      name: modelName,
      request_json: {
        model: 'fake/pong',
        temperature: 0.3,
        provider: { order: ['a', 'b', 'c'], allow_fallbacks: false },
      },
    },
  })
  expect(made.status()).toBe(201)
  const model = await made.json()

  async function cellOf(text: string, column: string) {
    const target = row(page, text)
    await expect(target).toBeVisible() // the rows are there, so are the headings: read them only now
    const heads = (await page.getByRole('table').locator('thead th').allInnerTexts()).map((h) => h.trim())
    const index = heads.indexOf(column)
    expect(index, `no column ${column} in ${heads.join(', ')}`).toBeGreaterThan(-1)
    const cell = target.locator('td').nth(index)
    const content = await cell.innerText()
    const [box, inner] = [(await cell.boundingBox())!, (await cell.locator('span').first().boundingBox())!]
    return { content, overflow: inner.x + inner.width - (box.x + box.width) }
  }

  try {
    await page.goto('/agents')
    const prompt = await cellOf(name, 'Prompt')
    expect(prompt.content).toBe('You are a very patient assistant. You...')
    expect(prompt.overflow).toBeLessThanOrEqual(0.5)

    await page.goto('/models')
    const settings = await cellOf(modelName, 'Settings')
    expect(settings.content.length).toBe(40)
    expect(settings.content.endsWith('...')).toBe(true)
    expect(settings.overflow).toBeLessThanOrEqual(0.5)
  } finally {
    await dropAgent(request, agent.id)
    await request.delete(`/api/v1/admin/models/${model.id}`, { headers: AUTH })
  }
})

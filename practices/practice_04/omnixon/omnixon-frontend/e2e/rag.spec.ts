import { readFile } from 'node:fs/promises'
import type { Page, Route } from '@playwright/test'
import { dialog, expect, field, test, toast } from './fixtures'

// The test stack has no embedding service, so entries cannot be made for real. The panel's behaviour is
// checked against a stand-in for /admin/rag: it lists, searches and takes entries like the service.

const entry = (id: number, content: string) => ({ id, agent_id: 1, content, embedding: null, metadata: {}, timestamp: '2026-01-01T00:00:00' })

interface Calls {
  gets: URL[]
  posts: string[]
  others: string[]
}

async function fakeKnowledgeBase(page: Page, texts: string[], opts: { reject?: string } = {}): Promise<Calls> {
  const calls: Calls = { gets: [], posts: [], others: [] }
  await page.route('**/api/v1/admin/rag**', async (route: Route) => {
    const req = route.request()
    const url = new URL(req.url())
    if (url.pathname !== '/api/v1/admin/rag') return route.continue()
    if (req.method() === 'GET') {
      calls.gets.push(url)
      if (url.searchParams.get('query')) return route.fulfill({ json: [entry(99, `closest to ${url.searchParams.get('query')}`)] })
      const offset = Number(url.searchParams.get('offset') ?? 0)
      const limit = Number(url.searchParams.get('limit') ?? 10)
      return route.fulfill({ json: texts.slice(offset, offset + limit).map((t, i) => entry(offset + i + 1, t)) })
    }
    if (req.method() === 'POST') {
      const content = (req.postDataJSON() as { content: string }).content
      calls.posts.push(content)
      if (opts.reject && content === opts.reject) return route.fulfill({ status: 502, json: { detail: 'Embedding failed' } })
      return route.fulfill({ status: 201, json: entry(1000 + calls.posts.length, content) })
    }
    calls.others.push(req.method())
    return route.continue()
  })
  return calls
}

const json = (value: unknown) => ({ name: 'knowledge.json', mimeType: 'application/json', buffer: Buffer.from(typeof value === 'string' ? value : JSON.stringify(value)) })

test('without a query the knowledge base lists every entry of the agent; with one it searches', async ({ page }) => {
  const calls = await fakeKnowledgeBase(page, ['Refunds take 5 days.', 'We ship worldwide.', 'Support is open on weekdays.'])
  await page.goto('/rag')
  // no search needed: everything of the selected agent is there
  for (const text of ['Refunds take 5 days.', 'We ship worldwide.', 'Support is open on weekdays.']) await expect(page.getByRole('row').filter({ hasText: text })).toBeVisible()
  expect(calls.gets[0].searchParams.get('query')).toBeNull()
  expect(calls.gets[0].searchParams.get('agent_id')).toBe('1') // the unit's own agent
  await expect(page.getByText('Search to see entries')).toHaveCount(0)

  // with a query: the existing search
  await field(page, 'Search', ).getByRole('textbox').fill('refund')
  await page.getByRole('button', { name: 'Search' }).click()
  await expect(page.getByRole('row').filter({ hasText: 'closest to refund' })).toBeVisible()
  await expect(page.getByRole('row').filter({ hasText: 'We ship worldwide.' })).toHaveCount(0)
  expect(calls.gets.at(-1)!.searchParams.get('query')).toBe('refund')

  // emptying the search brings everything back
  await field(page, 'Search').getByRole('textbox').fill('')
  await expect(page.getByRole('row').filter({ hasText: 'We ship worldwide.' })).toBeVisible()
})

test('an empty knowledge base says so', async ({ page }) => {
  await fakeKnowledgeBase(page, [])
  await page.goto('/rag')
  await expect(page.getByText('The knowledge base is empty')).toBeVisible()
})

test('a search that fails shows the service error', async ({ page }) => {
  await page.goto('/rag')
  await field(page, 'Search').getByRole('textbox').fill('refund policy')
  await page.getByRole('button', { name: 'Search' }).click()
  // no embedding service in the test stack
  await expect(page.getByText('Request failed')).toBeVisible()
  await expect(page.getByText(/Model provider error/)).toBeVisible()
})

test('export downloads the entries as a plain JSON array of strings, all of them', async ({ page }) => {
  // more than one page of 1000
  const texts = Array.from({ length: 1005 }, (_, i) => `entry ${i + 1}`)
  const calls = await fakeKnowledgeBase(page, texts)
  await page.goto('/rag')
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export JSON' }).click()])
  expect(download.suggestedFilename()).toMatch(/^knowledge-.*\.json$/)
  const body = JSON.parse(await readFile((await download.path())!, 'utf8'))
  expect(body).toEqual(texts) // strings only: no ids, timestamps or metadata, in the order they were made
  expect(calls.gets.filter((u) => u.searchParams.get('limit') === '1000').map((u) => u.searchParams.get('offset'))).toEqual(expect.arrayContaining(['0', '1000']))
  await expect(toast(page, 'Exported 1005 entries')).toBeVisible()
})

test('exporting an empty knowledge base gives an empty array', async ({ page }) => {
  await fakeKnowledgeBase(page, [])
  await page.goto('/rag')
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export JSON' }).click()])
  expect(JSON.parse(await readFile((await download.path())!, 'utf8'))).toEqual([])
})

test('import refuses a file that is not an array of strings, and says why', async ({ page }) => {
  const calls = await fakeKnowledgeBase(page, ['kept'])
  await page.goto('/rag')
  await page.getByRole('button', { name: 'Import JSON' }).click()
  const box = dialog(page, 'Import knowledge')
  const submit = box.getByRole('button', { name: /^Import/ , exact: false }).last()
  await expect(submit).toBeDisabled()

  const cases: [unknown, RegExp][] = [
    ['this is not json', /not valid JSON/],
    [{ items: ['a'] }, /Expected a JSON array of strings, but the file holds an object/],
    ['"just a string"', /holds a string/],
    [[], /array is empty/],
    [['fine', 5], /Item 2 is a number, not a string/],
    [['fine', { text: 'x' }], /Item 2 is an object/],
    [['fine', null], /Item 2 is null/],
    [['fine', ''], /Item 2 is an empty string/],
  ]
  for (const [content, message] of cases) {
    await box.locator('input[type=file]').setInputFiles(json(content))
    await expect(box).toContainText(message)
    await expect(submit).toBeDisabled()
  }
  expect(calls.posts).toEqual([]) // nothing was sent
  expect(calls.others).toEqual([]) // and nothing deleted: what was there stays
})

test('import adds every string as an entry and keeps what is there', async ({ page }) => {
  const calls = await fakeKnowledgeBase(page, ['already here'])
  await page.goto('/rag')
  await page.getByRole('button', { name: 'Import JSON' }).click()
  const box = dialog(page, 'Import knowledge')
  await box.locator('input[type=file]').setInputFiles(json(['Refunds take 5 days.', 'We ship worldwide.', 'Support is open on weekdays.']))
  await expect(box).toContainText('3 entries ready')
  await box.getByRole('button', { name: 'Import 3 entries' }).click()
  await expect(toast(page, 'Imported 3 entries')).toBeVisible()
  await expect(box).toHaveCount(0)
  expect([...calls.posts].sort()).toEqual(['Refunds take 5 days.', 'Support is open on weekdays.', 'We ship worldwide.'])
  expect(calls.others).toEqual([]) // no deletes or updates: existing entries are not touched
})

test('import reports the entries that failed and keeps the rest', async ({ page }) => {
  const calls = await fakeKnowledgeBase(page, [], { reject: 'bad one' })
  await page.goto('/rag')
  await page.getByRole('button', { name: 'Import JSON' }).click()
  const box = dialog(page, 'Import knowledge')
  await box.locator('input[type=file]').setInputFiles(json(['good one', 'bad one', 'another good one']))
  await box.getByRole('button', { name: 'Import 3 entries' }).click()
  await expect(toast(page, 'Imported 2 of 3; 1 failed')).toBeVisible()
  await expect(box.getByRole('alert')).toContainText('Item 2: Embedding failed')
  expect(calls.posts).toHaveLength(3)
})

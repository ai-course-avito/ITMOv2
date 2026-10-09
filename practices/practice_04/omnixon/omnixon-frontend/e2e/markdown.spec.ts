import { expect, field, singleResponse, test } from './fixtures'

// The answer of a model is markdown: it is shown rendered, and code is coloured like on GitHub. The test stack has no
// model that answers, so the service's /request is replaced by a canned answer.

const ANSWER = [
  '# A heading',
  '',
  'Some **bold**, some *italic*, ~~struck~~ and `inline_code()` with a [link](https://example.com/page).',
  '',
  '- first item',
  '- second item',
  '',
  '1. one',
  '2. two',
  '',
  '| Name | Role |',
  '| --- | --- |',
  '| ann | admin |',
  '',
  '> a quote',
  '',
  '```python',
  'import os',
  'def greet(name: str) -> str:',
  '    return f"hello {name}"  # say hi',
  '```',
  '',
  '```json',
  '{"ok": true, "count": 3}',
  '```',
  '',
  '```',
  'plain text in a fence',
  '```',
  '',
  '<script>window.hacked = 1</script>',
  '<img src=x onerror="window.hacked = 2">',
  '[bad](javascript:window.hacked=3)',
].join('\n')

async function answerWith(page: import('@playwright/test').Page, text: string) {
  await page.route('**/api/v1/request', (route) =>
    route.fulfill({ json: { response: text, user: { id: 1, agent_id: 1, external_id: 'md-user', timestamp: '2026-01-01T00:00:00' } } }),
  )
  await page.goto('/chat')
  await singleResponse(page)
  await page.getByPlaceholder(/Message…/).fill('show me')
  await page.getByRole('button', { name: 'Send' }).click()
}

test('the answer is rendered as markdown: headings, emphasis, lists, tables, quotes and links', async ({ page }) => {
  await answerWith(page, ANSWER)
  const md = page.locator('[data-slot=markdown]')
  await expect(md.getByRole('heading', { name: 'A heading' })).toBeVisible()
  await expect(md.locator('strong')).toHaveText('bold')
  await expect(md.locator('em')).toHaveText('italic')
  await expect(md.locator('del')).toHaveText('struck')
  await expect(md.getByRole('listitem').filter({ hasText: 'second item' })).toBeVisible()
  await expect(md.locator('ol li')).toHaveCount(2)
  await expect(md.getByRole('columnheader', { name: 'Role' })).toBeVisible()
  await expect(md.getByRole('cell', { name: 'admin' })).toBeVisible()
  await expect(md.locator('blockquote')).toHaveText('a quote')
  const link = md.getByRole('link', { name: 'link' })
  await expect(link).toHaveAttribute('href', 'https://example.com/page')
  await expect(link).toHaveAttribute('target', '_blank')
  await expect(link).toHaveAttribute('rel', /noopener/)
  // inline code is a chip of its own, not a block
  await expect(md.locator('p code', { hasText: 'inline_code()' })).toBeVisible()
})

test('fenced code is coloured like on GitHub, with its language and a copy button', async ({ page }) => {
  // the test panel is served over plain http, where a browser has no clipboard: a stand-in that keeps what was copied
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (t: string) => ((window as unknown as { copied: string }).copied = t) } })
  })
  await answerWith(page, ANSWER)
  const blocks = page.locator('[data-slot=code-block]')
  await expect(blocks).toHaveCount(3)

  const python = blocks.nth(0)
  await expect(python).toContainText('Python') // the language, above the code
  await expect(python.locator('pre.shiki')).toBeVisible() // highlighted (a plain block has no .shiki)
  const colors = await python.locator('pre.shiki span').evaluateAll((els) => els.filter((el) => el.childElementCount === 0).map((el) => [el.textContent ?? '', getComputedStyle(el).color] as const))
  const colorOf = (match: (text: string) => boolean) => colors.find(([text]) => match(text))?.[1] ?? 'none'
  const keyword = colorOf((t) => t.trim() === 'import')
  const string = colorOf((t) => t.includes('hello'))
  const comment = colorOf((t) => t.includes('say hi'))
  // GitHub's palette, light or dark: keyword red, string blue, comment grey
  expect(['rgb(207, 34, 46)', 'rgb(255, 123, 114)']).toContain(keyword)
  expect(['rgb(10, 48, 105)', 'rgb(165, 214, 255)']).toContain(string)
  expect(['rgb(110, 119, 129)', 'rgb(139, 148, 158)']).toContain(comment)
  expect(new Set([keyword, string, comment]).size).toBe(3) // three different colours, not one

  await expect(blocks.nth(1)).toContainText('JSON')
  await expect(blocks.nth(1).locator('pre.shiki')).toBeVisible()
  // no language: plain, in the same box
  await expect(blocks.nth(2)).toContainText('plain text in a fence')
  await expect(blocks.nth(2).locator('pre.shiki')).toHaveCount(0)

  // copying gives the code, not the markup
  await python.getByRole('button', { name: 'Copy code' }).click()
  await expect(python.getByRole('button', { name: 'Copy code' })).toContainText('Copied')
  expect(await page.evaluate(() => (window as unknown as { copied: string }).copied)).toBe('import os\ndef greet(name: str) -> str:\n    return f"hello {name}"  # say hi')
})

test('what the model writes is never run: HTML is text, bad links are dead, images are links', async ({ page }) => {
  await answerWith(page, ANSWER + '\n\n![a picture](https://example.com/p.png)')
  const md = page.locator('[data-slot=markdown]')
  await expect(md.getByRole('heading', { name: 'A heading' })).toBeVisible()
  expect(await page.evaluate(() => (window as unknown as { hacked?: number }).hacked)).toBeUndefined()
  await expect(md.locator('script, img')).toHaveCount(0) // not made into elements
  // the script text is there to read, as text
  await expect(md).toContainText('window.hacked = 1')
  // a javascript: link is not a link that runs
  const bad = md.getByText('bad')
  const href = await bad.evaluate((el) => (el.closest('a') ? el.closest('a')!.getAttribute('href') : null))
  expect(href === null || !href.startsWith('javascript:')).toBe(true)
  // an image is shown as a link to it (the browser does not fetch what a model names)
  await expect(md.getByRole('link', { name: 'a picture' })).toHaveAttribute('href', 'https://example.com/p.png')
})

test('only the answer is markdown: what the user types stays as typed', async ({ page }) => {
  await page.route('**/api/v1/request', (route) =>
    route.fulfill({ json: { response: 'ok', user: { id: 1, agent_id: 1, external_id: 'md-user', timestamp: '2026-01-01T00:00:00' } } }),
  )
  await page.goto('/chat')
  await singleResponse(page)
  await page.getByPlaceholder(/Message…/).fill('**not bold** and `not code`')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByText('**not bold** and `not code`')).toBeVisible()
  await expect(page.locator('strong')).toHaveCount(0)
  void field
})

test('a long line of code scrolls inside its box instead of widening the page', async ({ page }) => {
  await answerWith(page, '```bash\n' + 'echo ' + 'x'.repeat(600) + '\n```')
  const block = page.locator('[data-slot=code-block]')
  await expect(block).toBeVisible()
  const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
  expect(wide).toBe(false)
  expect(await block.locator('pre').evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true)
})

test('formulas in LaTeX are drawn: $...$ inline, $$...$$ as a block, and the \\( \\) and \\[ \\] forms', async ({ page }) => {
  await answerWith(
    page,
    [
      'Sorting takes $O(n \\log n)$ time.',
      '',
      '$$',
      '\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}',
      '$$',
      '',
      'Also \\(x^2 + y^2 = z^2\\) and a display:',
      '',
      '\\[ e^{i\\pi} + 1 = 0 \\]',
    ].join('\n'),
  )
  const md = page.locator('[data-slot=markdown]')
  await expect(md.locator('.katex')).toHaveCount(4) // inline, block, \( \), \[ \]
  await expect(md.locator('.katex-display')).toHaveCount(2) // the two blocks
  // KaTeX keeps the source as an annotation, so the formula can be read and copied
  await expect(md.locator('annotation[encoding="application/x-tex"]').first()).toHaveText('O(n \\log n)')
  await expect(md.locator('annotation[encoding="application/x-tex"]').nth(1)).toContainText('\\frac{n(n+1)}{2}')
  await expect(md.locator('annotation[encoding="application/x-tex"]').nth(2)).toHaveText('x^2 + y^2 = z^2')
  // drawn, not left as text: it has size
  const box = await md.locator('.katex').first().boundingBox()
  expect(box!.width).toBeGreaterThan(20)
  // no raw dollar signs or backslashes left around the formula
  await expect(md).not.toContainText('$O(')
})

test('prices are not formulas, and code with dollar signs stays code', async ({ page }) => {
  await answerWith(page, ['The plan costs $5 a month, or $50 a year, and $1,000.50 for a team.', '', '```bash', 'echo "$HOME $x$ \\(y\\)"', '```', '', 'Inline `$z$` too.'].join('\n'))
  const md = page.locator('[data-slot=markdown]')
  await expect(md.getByText('costs $5 a month, or $50 a year, and $1,000.50 for a team.')).toBeVisible()
  await expect(md.locator('.katex')).toHaveCount(0) // nothing was taken for maths
  await expect(md.locator('[data-slot=code-block]')).toContainText('echo "$HOME $x$ \\(y\\)"')
  await expect(md.locator('p code', { hasText: '$z$' })).toBeVisible()
})

test('a broken formula does not break the answer', async ({ page }) => {
  await answerWith(page, 'Before $\\frac{1}{$ after, and **still bold**.')
  const md = page.locator('[data-slot=markdown]')
  await expect(md.locator('strong')).toHaveText('still bold')
  await expect(md).toContainText('Before')
  await expect(md).toContainText('after')
})

test('the chain of calls shows the tools and their data, but not what the model wrote (that is the answer)', async ({ page }) => {
  await page.route('**/api/v1/request', (route) =>
    route.fulfill({
      json: {
        response: 'The final answer.',
        user: { id: 1, agent_id: 1, external_id: 'trace-user', timestamp: '2026-01-01T00:00:00' },
        trace: [
          { step: 1, kind: 'model', name: 'a/model', text: 'what-the-model-said-in-step-one', input_tokens: 10, output_tokens: 5, duration_ms: 800 },
          { step: 2, kind: 'tool', name: 'calculate', args: { a: 2, b: 3 }, result: '5', duration_ms: 12 },
          { step: 3, kind: 'model', name: 'a/model', text: 'what-the-model-said-in-step-three', input_tokens: 20, output_tokens: 8, duration_ms: 900 },
        ],
      },
    }),
  )
  await page.goto('/chat')
  await singleResponse(page)
  await page.getByPlaceholder(/Message…/).fill('add')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByText('The final answer.')).toBeVisible()
  await expect(page.getByText('3 steps')).toBeVisible()
  // the steps: the model calls (with tokens and time), and the tool with its arguments and result
  await expect(page.getByText('calculate')).toBeVisible()
  await expect(page.getByText('5', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('800 ms')).toBeVisible()
  await expect(page.getByText('10 in, 5 out')).toBeVisible()
  // but what the model wrote in its steps is not repeated
  await expect(page.getByText('what-the-model-said-in-step-one')).toHaveCount(0)
  await expect(page.getByText('what-the-model-said-in-step-three')).toHaveCount(0)
})

const SHIM_CLIPBOARD = () => {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (t: string) => ((window as unknown as { copied: string }).copied = t) } })
}

test('the text of an answer can be copied: its source, markdown and formulas as the model wrote them', async ({ page }) => {
  await page.addInitScript(SHIM_CLIPBOARD)
  const source = 'Energy is $E = mc^2$.\n\n```python\nprint("hi")\n```\n\n- **bold** item'
  await answerWith(page, source)
  await expect(page.locator('[data-slot=markdown] .katex')).toBeVisible()
  await page.getByRole('button', { name: 'Copy answer' }).click()
  expect(await page.evaluate(() => (window as unknown as { copied: string }).copied)).toBe(source) // not the rendered text
  // only the answer has the button: the user's own message and an error do not
  await expect(page.getByRole('button', { name: 'Copy answer' })).toHaveCount(1)
})

test('formulas of every shape a model writes are drawn, and none is shown as an error', async ({ page }) => {
  await answerWith(
    page,
    [
      '## Redshift',
      '',
      '| Case | Formula |',
      '| --- | --- |',
      '| Redshift | $1 + z = \\gamma(1-\\beta\\cos\\theta_o)$; receding: $1+z=\\sqrt{\\dfrac{1+\\beta}{1-\\beta}}$ |',
      '| Display | $$f = \\frac{c}{\\lambda}$$ |',
      '',
      'A sentence with a display $$a^2 + b^2 = c^2$$ in the middle, then **bold**.',
      '',
      '- a list item with $$x = \\frac{-b}{2a}$$ inside',
      '- and a price: it costs $5 or $1,000.50, not a formula, then $y_1$ is.',
      '',
      '$$',
      '\\begin{aligned}',
      'a &= b + c \\\\',
      'd &= e',
      '\\end{aligned}',
      '$$',
      '',
      'Chemistry: $\\ce{CH4 + 2O2 -> CO2 + 2H2O}$ at $25\\degree$.',
    ].join('\n'),
  )
  const md = page.locator('[data-slot=markdown]')
  await expect(md.locator('.katex').first()).toBeVisible()
  await expect(md.locator('.katex-error')).toHaveCount(0)
  // 2 in the first row, 1 in the second, 1 mid-sentence, 1 in the list, 1 plain $y_1$, 1 aligned block, 2 in the last line
  await expect(md.locator('.katex')).toHaveCount(9)
  // the prices are text, with their dollar signs
  await expect(md).toContainText('costs $5 or $1,000.50')
  // the aligned block is a centred display
  await expect(md.locator('.katex-display')).toHaveCount(2) // the mid-sentence one and the aligned one
  await expect(md.getByRole('cell').filter({ hasText: 'receding' }).locator('.katex')).toHaveCount(2)
})

test('a formula that is not finished (an answer cut off, or still arriving) is plain text, not an error', async ({ page }) => {
  await answerWith(page, 'Start $$\\frac{a}{b} and then it just stops, with $\\alpha')
  const md = page.locator('[data-slot=markdown]')
  await expect(md).toContainText('Start')
  await expect(md.locator('.katex-error')).toHaveCount(0)
  await expect(md.locator('.katex')).toHaveCount(0)
  await expect(md).toContainText('$$\\frac{a}{b} and then it just stops')
})

test('an answer has no card: nothing tells its edge from the page of the chat', async ({ page }) => {
  await answerWith(page, 'Just text.')
  const answer = page.getByTestId('answer')
  await expect(answer).toContainText('Just text.')
  const look = await answer.evaluate((el) => {
    const s = getComputedStyle(el)
    return { background: s.backgroundColor, borders: [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth], shadow: s.boxShadow }
  })
  expect(look.background).toBe('rgba(0, 0, 0, 0)') // the colour of the chat shows through
  expect(look.borders).toEqual(['0px', '0px', '0px', '0px'])
  expect(look.shadow).toBe('none')
  // what the user wrote keeps its bubble: it is the other side of the talk
  const mine = page.locator('div.bg-primary', { hasText: 'show me' })
  await expect(mine).toBeVisible()
})

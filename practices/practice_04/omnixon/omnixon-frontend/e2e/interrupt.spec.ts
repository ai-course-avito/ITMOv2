import { expect, fakeAgent, signInAs, test } from './fixtures'

test('Stop cuts the stream at once, marks the answer and keeps it in the history', async ({ browser, request }) => {
  const slow = await fakeAgent(request, 'fake/slow')
  const { page, context } = await signInAs(browser, slow.token)
  try {
    await page.goto('/chat')
    await page.getByPlaceholder(/Message…/).fill('Count slowly.')
    await page.getByRole('button', { name: 'Send' }).click()
    await expect(page.getByText(/word1/)).toBeVisible({ timeout: 15_000 }) // it is streaming
    const userId = (await page.getByTestId('chat-user').innerText()).trim()
    expect(userId).not.toBe('')

    await page.getByRole('button', { name: 'Stop' }).click()
    await expect(page.getByTestId('interrupted')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Stop' })).toHaveCount(0) // not running any more
    await expect(page.getByText(/word39/)).toHaveCount(0) // it was cut, not finished

    // the cut answer is in the history, marked
    const bearer = { Authorization: `Bearer ${slow.token}` }
    const [chat] = await (await request.get(`/api/v1/users/${userId}/chats`, { headers: bearer })).json() // the chat the Playground made
    const history = await (await request.get(`/api/v1/users/${userId}/chats/${chat.id}/history`, { headers: bearer })).json()
    expect(history.map((m: { content: { type: string } }) => m.content.type)).toEqual(['user', 'assistant'])
    expect(history[1].content.interrupted).toBe(true)
    expect(history[1].content.content).toContain('word0')

    // and the users page shows it
    await page.goto(`/users?user=${userId}`)
    await expect(page.getByText('interrupted', { exact: true })).toBeVisible()
  } finally {
    await context.close()
    await slow.drop()
  }
})

test('a new message while an answer is streaming cuts it and goes on', async ({ browser, request }) => {
  const slow = await fakeAgent(request, 'fake/slow')
  const { page, context } = await signInAs(browser, slow.token)
  try {
    await page.goto('/chat')
    await page.getByPlaceholder(/Message…/).fill('First question')
    await page.getByRole('button', { name: 'Send' }).click()
    await expect(page.getByText(/word1/)).toBeVisible({ timeout: 15_000 })
    const userId = (await page.getByTestId('chat-user').innerText()).trim()

    // the second message arrives by the API, as it would from a bot, for the same user and the chat
    const bearer = { Authorization: `Bearer ${slow.token}` }
    const [chat] = await (await request.get(`/api/v1/users/${userId}/chats`, { headers: bearer })).json()
    const second = await request.post('/api/v1/request', {
      headers: bearer,
      data: { user_id: userId, chat_id: chat.id, request: 'Second question' },
    })
    expect(second.status()).toBe(200)
    await expect(page.getByTestId('interrupted')).toBeVisible() // the panel saw its stream end as interrupted
    const history = await (await request.get(`/api/v1/users/${userId}/chats/${chat.id}/history`, { headers: bearer })).json()
    expect(history.map((m: { content: { type: string; interrupted?: boolean } }) => `${m.content.type}${m.content.interrupted ? '*' : ''}`)).toEqual(['user', 'assistant*', 'user', 'assistant'])
  } finally {
    await context.close()
    await slow.drop()
  }
})

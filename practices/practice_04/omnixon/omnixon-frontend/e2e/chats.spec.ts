import { closeSettings, dialog, expect, fakeAgent, field, openSettings, row, sidebar, signInAs, test, toast } from './fixtures'
import type { APIRequestContext, Page } from '@playwright/test'

// A model on the fake OpenAI-compatible server of the stack answers "pong" at once, so a conversation can be had without a key.

const send = async (page: Page, text: string) => {
  await page.getByPlaceholder(/Message…/).fill(text)
  await page.getByRole('button', { name: 'Send' }).click()
}
const items = (page: Page) => page.getByTestId('chat-item')
const withTitle = (page: Page, title: string) => items(page).filter({ hasText: title })
const storedState = (page: Page, agentId: number) => page.evaluate((id) => JSON.parse(localStorage.getItem(`omnixon.playground.agent.${id}`) ?? '{}'), agentId)

async function chatsOf(request: APIRequestContext, token: string, user: string) {
  return (await (await request.get(`/api/v1/users/${user}/chats`, { headers: { Authorization: `Bearer ${token}` } })).json()) as { id: number; title: string; messages: number; is_default: boolean }[]
}

test('the Playground remembers who it talks as and which chat, and shows the past of that chat when it opens', async ({ browser, request }) => {
  const fake = await fakeAgent(request, 'fake/pong')
  const { page, context } = await signInAs(browser, fake.token)
  try {
    await page.goto('/chat')
    await expect(page.getByTestId('chat-user')).toHaveText('new user')
    await expect(page.getByLabel('Chats')).toContainText('The first message starts a chat')
    await send(page, 'My first question')
    await expect(page.getByTestId('answer').first()).toContainText('pong')

    // a user was made for the messages, and a chat named after the first of them
    const user = (await page.getByTestId('chat-user').innerText()).trim()
    expect(user).toMatch(/^[0-9a-f]{32}$/)
    await expect(withTitle(page, 'My first question')).toHaveCount(1)
    await expect(withTitle(page, 'My first question')).toContainText('2 messages')
    const chats = await chatsOf(request, fake.token, user)
    expect(chats.map((c) => c.title)).toEqual(['My first question'])
    expect(await storedState(page, fake.agentId)).toEqual({ userId: user, chatId: chats[0].id })

    // after a reload it is the same user in the same chat, with the conversation in front of it
    await page.reload()
    await expect(page.getByTestId('chat-user')).toHaveText(user)
    await expect(page.getByText('My first question', { exact: true }).first()).toBeVisible()
    await expect(page.getByTestId('answer')).toHaveCount(1)
    await expect(page.getByTestId('answer')).toContainText('pong')
    await expect(withTitle(page, 'My first question')).toHaveAttribute('data-active', '')

    // the next message goes on in the same chat, as the same user
    await send(page, 'And the second one')
    await expect(page.getByTestId('answer')).toHaveCount(2)
    await expect(withTitle(page, 'My first question')).toContainText('4 messages')
    expect(await chatsOf(request, fake.token, user)).toHaveLength(1)
  } finally {
    await context.close()
    await fake.drop()
  }
})

test('chats are separate threads: a new chat starts blank, the old ones come back when picked, and they can be renamed, cleared and deleted', async ({ browser, request }) => {
  const fake = await fakeAgent(request, 'fake/pong')
  const { page, context } = await signInAs(browser, fake.token)
  try {
    await page.goto('/chat')
    await send(page, 'About apples')
    await expect(page.getByTestId('answer')).toHaveCount(1)

    await page.getByRole('button', { name: 'New chat' }).click()
    await expect(page.getByText('Say something', { exact: true })).toBeVisible() // a blank page, the same user
    await send(page, 'About bananas')
    await expect(page.getByTestId('answer')).toHaveCount(1)
    await expect(items(page)).toHaveCount(2)
    await expect(items(page).first()).toContainText('About bananas') // the latest first
    const user = (await page.getByTestId('chat-user').innerText()).trim()

    // picking the first chat shows its conversation and not the other one
    await withTitle(page, 'About apples').getByTestId('chat-open').click()
    const said = (text: string) => page.locator('div.bg-primary', { hasText: text }) // what the user wrote, in the transcript (not the title in the list)
    await expect(said('About apples')).toBeVisible()
    await expect(said('About bananas')).toHaveCount(0)
    await expect(withTitle(page, 'About apples')).toHaveAttribute('data-active', '')

    // rename
    await page.getByRole('button', { name: 'Actions for About apples' }).click()
    await page.getByRole('menuitem', { name: 'Rename' }).click()
    await field(dialog(page, 'Rename chat'), 'Name').getByRole('textbox').fill('Fruit talk')
    await dialog(page, 'Rename chat').getByRole('button', { name: 'Save' }).click()
    await expect(toast(page, 'Chat renamed')).toBeVisible()
    await expect(withTitle(page, 'Fruit talk')).toHaveCount(1)
    expect((await chatsOf(request, fake.token, user)).map((c) => c.title).sort()).toEqual(['About bananas', 'Fruit talk'])

    // clear the messages of the chat: it stays, empty
    await page.getByRole('button', { name: 'Actions for Fruit talk' }).click()
    await page.getByRole('menuitem', { name: 'Clear messages' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Clear' }).click()
    await expect(toast(page, 'Chat cleared')).toBeVisible()
    await expect(withTitle(page, 'Fruit talk')).toContainText('0 messages')
    await expect(page.getByText('Say something', { exact: true })).toBeVisible()

    // delete the open chat: the other one is open then
    await page.getByRole('button', { name: 'Actions for Fruit talk' }).click()
    await page.getByRole('menuitem', { name: 'Delete' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click()
    await expect(toast(page, 'Chat deleted')).toBeVisible()
    await expect(items(page)).toHaveCount(1)
    await expect(withTitle(page, 'About bananas')).toHaveAttribute('data-active', '')
    await expect(page.locator('div.bg-primary', { hasText: 'About bananas' })).toBeVisible()
  } finally {
    await context.close()
    await fake.drop()
  }
})

test('another user can be picked in the settings: their chats are listed and their last conversation is shown', async ({ browser, request }) => {
  const fake = await fakeAgent(request, 'fake/pong')
  const bearer = { Authorization: `Bearer ${fake.token}` }
  const ask = (user: string, text: string, chat_id?: number) => request.post('/api/v1/request', { headers: bearer, data: { user_id: user, request: text, chat_id } })
  const { page, context } = await signInAs(browser, fake.token)
  try {
    expect((await ask('chat-pick-ann', 'Ann asks one')).status()).toBe(200) // the default chat, as a bot would
    await request.post('/api/v1/users/chat-pick-ann/chats', { headers: bearer, data: { title: 'Ann in the panel' } })
    const panel = (await chatsOf(request, fake.token, 'chat-pick-ann')).find((c) => c.title === 'Ann in the panel')!
    expect((await ask('chat-pick-ann', 'Ann asks two', panel.id)).status()).toBe(200)

    await page.goto('/chat')
    await send(page, 'I am somebody else')
    await expect(page.getByTestId('answer')).toHaveCount(1)

    const settings = await openSettings(page)
    await field(settings, 'User id').getByRole('combobox').fill('chat-pick-ann')
    await closeSettings(page)
    await expect(page.getByTestId('chat-user')).toHaveText('chat-pick-ann')
    await expect(items(page)).toHaveCount(2)
    // the latest chat is open, with its past
    await expect(withTitle(page, 'Ann in the panel')).toHaveAttribute('data-active', '')
    await expect(page.getByText('Ann asks two', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('I am somebody else', { exact: true })).toHaveCount(0)
    // the other, the default chat of a bot
    await withTitle(page, 'Default chat').getByTestId('chat-open').click()
    await expect(page.getByText('Ann asks one', { exact: true }).first()).toBeVisible()
    await expect(withTitle(page, 'Default chat')).toContainText('default')
  } finally {
    await context.close()
    await request.delete('/api/v1/users/chat-pick-ann', { headers: bearer })
    await fake.drop()
  }
})

test('what is remembered may be out of date: a chat or a user that is gone does not break the page', async ({ browser, request }) => {
  const fake = await fakeAgent(request, 'fake/pong')
  const { page, context } = await signInAs(browser, fake.token)
  try {
    await page.addInitScript((id) => localStorage.setItem(`omnixon.playground.agent.${id}`, JSON.stringify({ userId: 'gone-user-xyz', chatId: 987654 })), fake.agentId)
    await page.goto('/chat')
    await expect(page.getByTestId('chat-user')).toHaveText('gone-user-xyz') // it is still the user to write as ...
    await expect(items(page)).toHaveCount(0) // ... who has no chats (yet)
    await expect(page.getByText('Say something', { exact: true })).toBeVisible()
    // writing creates the user that was not there, and a chat
    await send(page, 'Hello again')
    await expect(page.getByTestId('answer')).toHaveCount(1)
    await expect(items(page)).toHaveCount(1)
    expect((await chatsOf(request, fake.token, 'gone-user-xyz')).map((c) => c.title)).toEqual(['Hello again'])
  } finally {
    await context.close()
    await request.delete('/api/v1/users/gone-user-xyz', { headers: { Authorization: `Bearer ${fake.token}` } })
    await fake.drop()
  }
})

test('a regular token has the users of its agent and their chats: it looks them up, renames, deletes and manages their chats, and calls nothing of /admin', async ({ browser, request }) => {
  const fake = await fakeAgent(request, 'fake/pong', 'regular')
  const bearer = { Authorization: `Bearer ${fake.token}` }
  const ask = (user: string, text: string, chat_id?: number) => request.post('/api/v1/request', { headers: bearer, data: { user_id: user, request: text, chat_id } })
  const { page, context, adminCalls } = await signInAs(browser, fake.token)
  try {
    expect((await ask('reg-ann', 'Ann one')).status()).toBe(200)
    await request.post('/api/v1/users/reg-ann/chats', { headers: bearer, data: { title: 'Second thread' } })
    const second = (await chatsOf(request, fake.token, 'reg-ann')).find((c) => c.title === 'Second thread')!
    expect((await ask('reg-ann', 'Ann two', second.id)).status()).toBe(200)

    await expect(page.getByRole('heading', { name: 'Playground' })).toBeVisible() // it starts on the Playground
    await sidebar(page).getByRole('link', { name: 'Users & history', exact: true }).click()
    await expect(page).toHaveURL(/\/users$/)

    // the users that wrote lately, and a new one
    await expect(row(page, 'reg-ann')).toContainText('4')
    await page.getByRole('button', { name: 'New user' }).click()
    await field(dialog(page, 'New user'), 'External id').getByRole('textbox').fill('reg-bob')
    await dialog(page, 'New user').getByRole('button', { name: 'Save' }).click()
    await expect(toast(page, 'User created')).toBeVisible()
    await expect(page.getByText('No chats yet', { exact: true })).toBeVisible()
    // chats of a user are made here too
    await page.getByRole('button', { name: 'New chat' }).click()
    await expect(toast(page, 'Chat started')).toBeVisible()
    await expect(items(page)).toHaveCount(1)
    await page.getByRole('button', { name: 'Rename' }).first().click()
    await field(dialog(page, 'Rename user'), 'External id').getByRole('textbox').fill('reg-bobby')
    await dialog(page, 'Rename user').getByRole('button', { name: 'Save' }).click()
    await expect(toast(page, 'User renamed')).toBeVisible()
    await expect(items(page)).toHaveCount(1) // the chats followed the new name

    // ann: two chats; the open one is the latest, and its messages are shown
    await page.goto('/users?user=reg-ann')
    await expect(items(page)).toHaveCount(2)
    await expect(page.getByTestId('chat-title')).toHaveText('Second thread')
    await expect(page.getByText('Ann two', { exact: true })).toBeVisible()
    await withTitle(page, 'Default chat').getByTestId('chat-open').click()
    await expect(page.getByTestId('chat-title')).toHaveText('Default chat')
    await expect(page.getByText('Ann one', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Actions for Second thread' }).click()
    await page.getByRole('menuitem', { name: 'Delete' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click()
    await expect(toast(page, 'Chat deleted')).toBeVisible()
    await expect(items(page)).toHaveCount(1)
    expect((await chatsOf(request, fake.token, 'reg-ann')).map((c) => c.title)).toEqual(['Default chat'])

    // deleting the user: gone with everything
    await page.getByRole('button', { name: /Delete/ }).first().click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click()
    await expect(toast(page, 'User deleted')).toBeVisible()
    expect((await request.get('/api/v1/users/reg-ann', { headers: bearer })).status()).toBe(404)
    expect(adminCalls).toEqual([])
  } finally {
    await context.close()
    for (const user of ['reg-ann', 'reg-bob', 'reg-bobby']) await request.delete(`/api/v1/users/${user}`, { headers: bearer })
    await fake.drop()
  }
})

import { expect, singleResponse, test, TOKEN } from './fixtures'

// The test panel is served over plain http at http://panel, which a browser does not trust with the microphone, so the
// page gets a stand-in microphone: a real MediaStream made of a tone (Web Audio). Everything after it is the real
// recording: MediaRecorder, the waveform, the decoding and the encoding of the WAV file.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: async () => {
          const context = new AudioContext()
          const tone = context.createOscillator()
          tone.frequency.value = 440
          const out = context.createMediaStreamDestination()
          tone.connect(out)
          tone.start()
          return out.stream
        },
      },
    })
  })
})

async function record(page: import('@playwright/test').Page, ms = 1300) {
  await page.getByRole('button', { name: 'Record voice' }).click()
  const bar = page.getByRole('group', { name: 'Recording' })
  // if the recording does not start, the panel says why in a toast: show it instead of a bare timeout
  const refused = page.locator('[data-sonner-toast]').first()
  await expect(bar.or(refused)).toBeVisible()
  if (!(await bar.isVisible())) throw new Error(`the recording did not start: ${await refused.innerText()}`)
  await page.waitForTimeout(ms)
  return bar
}

test('a voice message is recorded, kept as a WAV file in the message, and can be listened to', async ({ page }) => {
  await page.goto('/chat')
  const bar = await record(page)
  await expect(bar.getByLabel('Recording time')).not.toHaveText('0:00')
  await bar.getByRole('button', { name: 'Attach' }).click()

  const chip = page.getByText(/voice-.*\.wav/)
  await expect(chip).toBeVisible()
  await expect(page.getByLabel(/Listen to voice-.*\.wav/)).toBeVisible()
  // nothing was sent yet, and the message can go with some text
  await expect(page.getByText('Say something', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Send' })).toBeEnabled() // a file alone is enough
})

test('"Send" ends the recording and sends it at once as a WAV file; the answer of a model that cannot hear it is shown as an error', async ({ page }) => {
  await page.goto('/chat')
  await singleResponse(page)
  const sent = page.waitForRequest((r) => r.url().endsWith('/api/v1/request') && r.method() === 'POST')
  const bar = await record(page)
  await bar.getByRole('button', { name: 'Send' }).click()

  const body = (await sent).postDataJSON() as { attachments: { media_type: string; name: string; data: string }[] }
  expect(body.attachments).toHaveLength(1)
  const file = body.attachments[0]
  expect(file.media_type).toBe('audio/wav')
  expect(file.name).toMatch(/^voice-.*\.wav$/)
  // a real WAV: RIFF....WAVE, PCM, one channel, 16 bits
  const bytes = Buffer.from(file.data, 'base64')
  expect(bytes.subarray(0, 4).toString()).toBe('RIFF')
  expect(bytes.subarray(8, 12).toString()).toBe('WAVE')
  expect(bytes.readUInt16LE(20)).toBe(1) // PCM
  expect(bytes.readUInt16LE(22)).toBe(1) // mono
  expect(bytes.readUInt16LE(34)).toBe(16) // bits per sample
  expect(bytes.length).toBeGreaterThan(10_000) // more than a header: about a second of sound

  // no key in the test stack: the service answers with the provider's error, shown like any other
  await expect(page.getByText(/Model provider error/)).toBeVisible()
  await expect(page.getByText(/voice-.*\.wav/).first()).toBeVisible() // the transcript says a file went along
})

test('a recording can be thrown away', async ({ page }) => {
  await page.goto('/chat')
  const bar = await record(page, 400)
  await bar.getByRole('button', { name: 'Discard the recording' }).click()
  await expect(page.getByRole('button', { name: 'Record voice' })).toBeVisible()
  await expect(page.getByText(/voice-.*\.wav/)).toHaveCount(0)
})

test('without a microphone the panel says so and nothing breaks', async ({ browser }) => {
  const context = await browser.newContext()
  await context.addInitScript((token) => {
    localStorage.setItem('omnixon.token', token)
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: () => Promise.reject(new Error('Permission denied')) } })
  }, TOKEN)
  const page = await context.newPage()
  try {
    await page.goto('/chat')
    await page.getByRole('button', { name: 'Record voice' }).click()
    await expect(page.locator('[data-sonner-toast]').filter({ hasText: /microphone is not available/ }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Record voice' })).toBeVisible()
  } finally {
    await context.close()
  }
})

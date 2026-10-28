import { dialog, expect, field, row, test, toast, unique } from './fixtures'

test('memories: create, list, edit, forget', async ({ page }) => {
  const user = unique('e2e-mem')
  const fact = unique('likes tea')
  const edited = `${fact} (green)`

  await page.goto('/users')
  await page.getByRole('button', { name: 'New user' }).click()
  await field(dialog(page, 'New user'), 'External id').getByRole('textbox').fill(user)
  await dialog(page, 'New user').getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'User created')).toBeVisible()

  await page.getByRole('main').getByRole('button', { name: 'Memories' }).click()
  await expect(page).toHaveURL(new RegExp(`memories\\?user=${user}`))
  await expect(page.getByText('Nothing remembered')).toBeVisible()

  await page.getByRole('button', { name: 'New memory' }).click()
  await dialog(page, 'New memory').getByRole('textbox').fill(fact)
  await dialog(page, 'New memory').getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'Memory saved')).toBeVisible()
  await expect(row(page, fact)).toBeVisible()

  await row(page, fact).getByRole('button', { name: 'Edit' }).click()
  const edit = dialog(page, /Memory \d+/)
  await expect(edit.getByRole('textbox')).toHaveValue(fact)
  await edit.getByRole('textbox').fill(edited)
  await edit.getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'Memory updated')).toBeVisible()
  await expect(row(page, edited)).toBeVisible()

  await row(page, edited).getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Forget' }).click()
  await expect(toast(page, 'Memory deleted')).toBeVisible()
  await expect(row(page, edited)).toHaveCount(0)
})

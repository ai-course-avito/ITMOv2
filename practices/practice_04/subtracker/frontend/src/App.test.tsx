import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createState, installMockApi, signIn, type MockState } from './test/mockApi'
import { renderApp } from './test/renderApp'

let state: MockState

beforeEach(() => {
  state = createState()
})
afterEach(() => vi.unstubAllGlobals())

const setup = (path = '/', over: Partial<MockState> = {}, authed = true) => {
  state = createState(over)
  installMockApi(state)
  if (authed) signIn()
  return { user: userEvent.setup(), ...renderApp(path) }
}

describe('auth flow', () => {
  it('redirects an anonymous visitor to the login form', async () => {
    setup('/subscriptions', {}, false)
    expect(await screen.findByRole('heading', { name: 'С возвращением' })).toBeInTheDocument()
  })

  it('redirects a signed-in user away from the login page', async () => {
    setup('/login')
    expect(await screen.findByTestId('monthly-total')).toHaveTextContent('$82.10')
  })

  it('signs in and shows the overview', async () => {
    const { user } = setup('/login', {}, false)
    await user.type(await screen.findByLabelText('Email'), 'demo@example.com')
    await user.type(screen.getByLabelText('Пароль'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Войти' }))
    expect(await screen.findByTestId('monthly-total')).toBeInTheDocument()
    expect(localStorage.getItem('subtracker.session')).toContain('refreshToken')
  })

  it('shows one neutral message for wrong credentials and stays on the form', async () => {
    const { user } = setup('/login', { loginStatus: 401 }, false)
    await user.type(await screen.findByLabelText('Email'), 'a@b.co')
    await user.type(screen.getByLabelText('Пароль'), 'wrong-password')
    await user.click(screen.getByRole('button', { name: 'Войти' }))
    expect(await screen.findByText('Неверный email или пароль')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'С возвращением' })).toBeInTheDocument()
  })

  it('does not call the backend for a short password on registration', async () => {
    const { user } = setup('/login', {}, false)
    await user.click(await screen.findByRole('tab', { name: 'Регистрация' }))
    await user.type(screen.getByLabelText('Email'), 'new@example.com')
    await user.type(screen.getByLabelText(/Пароль/), 'short')
    await user.click(screen.getByRole('button', { name: 'Зарегистрироваться' }))
    expect(await screen.findByText('Пароль должен быть не короче 8 символов')).toBeInTheDocument()
    expect(state.calls.some((c) => c.path === '/api/auth/register')).toBe(false)
  })

  it('shows a message when the email is already taken', async () => {
    const { user } = setup('/login', { registerStatus: 409 }, false)
    await user.click(await screen.findByRole('tab', { name: 'Регистрация' }))
    await user.type(screen.getByLabelText('Email'), 'taken@example.com')
    await user.type(screen.getByLabelText(/Пароль/), 'password123')
    await user.click(screen.getByRole('button', { name: 'Зарегистрироваться' }))
    expect(await screen.findByText('Этот email уже зарегистрирован')).toBeInTheDocument()
  })

  it('signs out and removes the session', async () => {
    const { user } = setup('/')
    await screen.findByTestId('monthly-total')
    await user.click(screen.getAllByRole('button', { name: 'Выйти' })[0]!)
    expect(await screen.findByRole('heading', { name: 'С возвращением' })).toBeInTheDocument()
    expect(localStorage.getItem('subtracker.session')).toBeNull()
  })
})

describe('appearance', () => {
  it('uses the dark theme and Russian on the first visit', async () => {
    setup('/login', {}, false)
    await screen.findByRole('heading', { name: 'С возвращением' })
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(document.documentElement.lang).toBe('ru')
  })

  it('switches theme and language and remembers them', async () => {
    const { user } = setup('/login', {}, false)
    await user.click((await screen.findAllByRole('button', { name: 'Сменить тему' }))[0]!)
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('subtracker.theme')).toBe('light')
    await user.click(screen.getAllByRole('button', { name: 'EN' })[0]!)
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    expect(localStorage.getItem('subtracker.lang')).toBe('en')
  })

  it('shows the ad banner on Free and hides it on Pro', async () => {
    setup('/', { plan: 'free' })
    await screen.findByTestId('monthly-total')
    expect(screen.getByTestId('ad-banner')).toBeInTheDocument()
  })

  it('hides the ad banner on Pro', async () => {
    setup('/', { plan: 'pro' })
    await screen.findByTestId('monthly-total')
    expect(screen.queryByTestId('ad-banner')).not.toBeInTheDocument()
  })

  it('keeps the Calendar tab locked and without navigation', async () => {
    const { user } = setup('/')
    await screen.findByTestId('monthly-total')
    const tab = screen.getAllByRole('button', { name: /Календарь/ })[0]!
    expect(tab).toHaveAttribute('aria-disabled', 'true')
    await user.click(tab)
    expect(screen.getByTestId('monthly-total')).toBeInTheDocument()
  })
})

describe('overview', () => {
  it('shows totals from the backend, active and paused counts', async () => {
    setup('/')
    expect(await screen.findByTestId('monthly-total')).toHaveTextContent('$82.10')
    expect(screen.getByTestId('yearly-total')).toHaveTextContent('$985.20')
    expect(screen.getByTestId('active-count')).toHaveTextContent('3')
    expect(screen.getByTestId('paused-hint')).toHaveTextContent('приостановлено: 1')
  })

  it('describes the donut chart as text and limits the top list to five', async () => {
    setup('/', {
      subs: Array.from({ length: 7 }, (_, i) =>
        sub7(i + 1),
      ),
    })
    const chart = await screen.findByRole('img')
    expect(chart.getAttribute('aria-label')).toContain('Sub 1')
    expect(screen.getAllByTestId('top-bar')).toHaveLength(5)
    expect(screen.getAllByTestId('top-bar')[0]).toHaveStyle({ width: '100%' })
  })

  it('reloads upcoming charges when the period changes', async () => {
    const { user } = setup('/')
    await screen.findByTestId('monthly-total')
    await user.click(screen.getByRole('button', { name: '7 дней' }))
    await waitFor(() =>
      expect(state.calls.filter((c) => c.path === '/api/subscriptions/upcoming').at(-1)?.query.get('days')).toBe('7'),
    )
  })

  it('invites to add the first subscription when there are none', async () => {
    setup('/', { subs: [] })
    expect(await screen.findByText('Пока нет подписок')).toBeInTheDocument()
  })

  it('shows an error with a retry when the backend is unreachable', async () => {
    setup('/')
    await screen.findByTestId('monthly-total')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const { user } = { user: userEvent.setup() }
    await user.click(screen.getAllByRole('button', { name: 'EN' })[0]!)
    // trigger a reload through the period switch
    await user.click(screen.getByRole('button', { name: '7 days' }))
    expect(await screen.findByText(/Could not reach the server/)).toBeInTheDocument()
  })
})

function sub7(i: number) {
  return {
    id: i,
    name: `Sub ${i}`,
    amount: String(30 - i),
    billing_cycle: 'monthly',
    custom_interval_days: null,
    is_active: true,
    start_date: '2026-01-01',
    next_billing_date: '2026-10-20',
    note: null,
    monthly_cost: `${30 - i}.00`,
    charge_date: '2026-10-20',
    days_until: 4,
  }
}

describe('subscriptions screen', () => {
  it('groups subscriptions by time to charge and puts paused ones last', async () => {
    setup('/subscriptions')
    const week = await screen.findByTestId('group-week')
    expect(within(week).getByText('Gym')).toBeInTheDocument()
    expect(within(week).getByText('Netflix')).toBeInTheDocument()
    expect(within(screen.getByTestId('group-later')).getByText('iCloud+')).toBeInTheDocument()
    expect(within(screen.getByTestId('group-paused')).getByText('Notion')).toBeInTheDocument()
    expect(screen.queryByTestId('group-today')).not.toBeInTheDocument()
  })

  it('sorts by the nearest charge by default and sends filters to the backend', async () => {
    const { user } = setup('/subscriptions')
    await screen.findByTestId('group-week')
    expect(state.calls.find((c) => c.path === '/api/subscriptions')?.query.get('sort')).toBe('charge_date')
    await user.click(screen.getByRole('button', { name: 'Активные' }))
    await user.click(screen.getByRole('button', { name: 'Год' }))
    await waitFor(() => {
      const last = state.calls.filter((c) => c.method === 'GET' && c.path === '/api/subscriptions').at(-1)!
      expect(last.query.get('is_active')).toBe('true')
      expect(last.query.get('billing_cycle')).toBe('yearly')
    })
    expect(await screen.findByText('iCloud+')).toBeInTheDocument()
    expect(screen.queryByText('Gym')).not.toBeInTheDocument()
  })

  it('searches after a short pause', async () => {
    const { user } = setup('/subscriptions')
    await screen.findByTestId('group-week')
    await user.type(screen.getByRole('searchbox', { name: 'Поиск' }), 'netf')
    await waitFor(() => expect(screen.queryByText('Gym')).not.toBeInTheDocument())
    expect(screen.getByText('Netflix')).toBeInTheDocument()
    const searches = state.calls.filter((c) => c.path === '/api/subscriptions' && c.query.get('q'))
    expect(searches.at(-1)?.query.get('q')).toBe('netf')
  })

  it('remembers the card view after a reload', async () => {
    const { user, unmount } = setup('/subscriptions')
    await screen.findByTestId('group-week')
    await user.click(screen.getByRole('button', { name: 'Карточки' }))
    expect(localStorage.getItem('subtracker.view')).toBe('cards')
    unmount()
    renderApp('/subscriptions')
    expect(await screen.findByRole('button', { name: 'Карточки' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('pauses a subscription and moves it to the paused group', async () => {
    const { user } = setup('/subscriptions')
    await screen.findByTestId('group-week')
    await user.click(screen.getByRole('button', { name: /Действия: Netflix/ }))
    await user.click(screen.getByRole('menuitem', { name: 'Приостановить' }))
    await waitFor(() => expect(within(screen.getByTestId('group-paused')).getByText('Netflix')).toBeInTheDocument())
    expect(state.calls.find((c) => c.method === 'PATCH')?.body).toEqual({ is_active: false })
  })

  it('keeps the subscription when deletion is declined', async () => {
    const { user } = setup('/subscriptions')
    await screen.findByTestId('group-week')
    await user.click(screen.getByRole('button', { name: /Действия: Gym/ }))
    await user.click(screen.getByRole('menuitem', { name: 'Удалить' }))
    const dialog = screen.getByRole('alertdialog')
    await user.click(within(dialog).getByRole('button', { name: 'Отмена' }))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(state.calls.some((c) => c.method === 'DELETE')).toBe(false)
    expect(screen.getByText('Gym')).toBeInTheDocument()
  })

  it('deletes a subscription after confirmation', async () => {
    const { user } = setup('/subscriptions')
    await screen.findByTestId('group-week')
    await user.click(screen.getByRole('button', { name: /Действия: Gym/ }))
    await user.click(screen.getByRole('menuitem', { name: 'Удалить' }))
    await user.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Удалить' }))
    await waitFor(() => expect(screen.queryByText('Gym')).not.toBeInTheDocument())
    expect(state.calls.some((c) => c.method === 'DELETE' && c.path === '/api/subscriptions/1')).toBe(true)
  })
})

describe('subscription panel', () => {
  const openPanel = async () => {
    const ctx = setup('/subscriptions')
    await screen.findByTestId('group-week')
    await ctx.user.click(screen.getAllByRole('button', { name: 'Добавить' })[0]!)
    return { ...ctx, dialog: await screen.findByRole('dialog') }
  }

  it('creates a subscription and shows it in the list', async () => {
    const { user, dialog } = await openPanel()
    await user.type(within(dialog).getByLabelText('Название'), 'Яндекс Плюс')
    await user.type(within(dialog).getByLabelText('Сумма платежа'), '299,5')
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(state.calls.find((c) => c.method === 'POST' && c.path === '/api/subscriptions')?.body).toMatchObject({
      name: 'Яндекс Плюс',
      amount: '299.50',
      billing_cycle: 'monthly',
      custom_interval_days: null,
    })
    expect(await screen.findByText('Яндекс Плюс')).toBeInTheDocument()
  })

  it('validates the fields before calling the backend', async () => {
    const { user, dialog } = await openPanel()
    await user.type(within(dialog).getByLabelText('Сумма платежа'), '0')
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    expect(within(dialog).getByText('Введите название (до 255 символов)')).toBeInTheDocument()
    expect(within(dialog).getByText(/Сумма должна быть больше 0/)).toBeInTheDocument()
    expect(state.calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('shows the custom interval field only for the custom cycle', async () => {
    const { user, dialog } = await openPanel()
    expect(within(dialog).queryByLabelText(/Раз в сколько дней/)).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Свой' }))
    expect(within(dialog).getByLabelText(/Раз в сколько дней/)).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Год' }))
    expect(within(dialog).queryByLabelText(/Раз в сколько дней/)).not.toBeInTheDocument()
  })

  it('requires 1..3650 days for the custom cycle', async () => {
    const { user, dialog } = await openPanel()
    await user.type(within(dialog).getByLabelText('Название'), 'VPN')
    await user.type(within(dialog).getByLabelText('Сумма платежа'), '19.90')
    await user.click(within(dialog).getByRole('button', { name: 'Свой' }))
    await user.type(within(dialog).getByLabelText(/Раз в сколько дней/), '4000')
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    expect(within(dialog).getByText('Введите число дней от 1 до 3650')).toBeInTheDocument()
    expect(state.calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('keeps the panel open and marks the field when the backend answers 422', async () => {
    state = createState({
      createResponse: { status: 422, body: { detail: [{ loc: ['body', 'amount'], msg: 'bad', type: 'x' }] } },
    })
    installMockApi(state)
    signIn()
    const user = userEvent.setup()
    renderApp('/subscriptions')
    await screen.findByTestId('group-week')
    await user.click(screen.getAllByRole('button', { name: 'Добавить' })[0]!)
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Название'), 'Test')
    await user.type(within(dialog).getByLabelText('Сумма платежа'), '5')
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    expect(await within(dialog).findByText('Сервер не принял значение')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('closes on Escape without saving and returns focus to the opener', async () => {
    const { user } = await openPanel()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(state.calls.some((c) => c.method === 'POST')).toBe(false)
    expect(document.activeElement).toBe(screen.getAllByRole('button', { name: 'Добавить' })[0])
  })

  it('opens filled with the values when editing', async () => {
    const { user } = setup('/subscriptions')
    await screen.findByTestId('group-week')
    await user.click(screen.getByRole('button', { name: /Действия: Netflix/ }))
    await user.click(screen.getByRole('menuitem', { name: 'Изменить' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByLabelText('Название')).toHaveValue('Netflix')
    expect(within(dialog).getByLabelText('Сумма платежа')).toHaveValue('15.49')
  })
})

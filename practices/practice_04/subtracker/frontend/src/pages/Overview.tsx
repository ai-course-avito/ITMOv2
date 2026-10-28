import { useMemo, useState } from 'react'
import { api } from '../api/endpoints'
import { messageFor } from '../api/errors'
import type { SubscriptionShare } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { useDataVersion } from '../components/DataVersion'
import { Donut, type Segment } from '../components/Donut'
import { usePanel } from '../components/panelContext'
import { useAsync } from '../components/useAsync'
import { useI18n } from '../i18n'
import { formatDay } from '../lib/dates'
import { formatMoney, shareOfMax } from '../lib/money'
import { colorAt } from '../lib/palette'

const MAX_SEGMENTS = 6

function toSegments(items: SubscriptionShare[], othersLabel: string): Segment[] {
  if (items.length <= MAX_SEGMENTS) return items.map((i) => ({ name: i.name, share: i.sharePercent }))
  const head = items.slice(0, MAX_SEGMENTS - 1)
  const rest = items.slice(MAX_SEGMENTS - 1)
  const restShare = rest.reduce((sum, i) => sum + Number(i.sharePercent), 0).toFixed(2)
  return [...head.map((i) => ({ name: i.name, share: i.sharePercent })), { name: othersLabel, share: restShare }]
}

function ErrorBox({ message, onRetry, retry }: { message: string; onRetry: () => void; retry: string }) {
  return (
    <div role="alert" className="card rounded-3xl p-8 text-center">
      <p className="mb-4 text-muted">{message}</p>
      <button type="button" onClick={onRetry} className="rounded-full bg-accent px-6 py-3 text-sm font-semibold text-accent-text">
        {retry}
      </button>
    </div>
  )
}

export default function Overview() {
  const { t, locale } = useI18n()
  const { user } = useAuth()
  const { version } = useDataVersion()
  const panel = usePanel()
  const [period, setPeriod] = useState<7 | 30>(30)

  const main = useAsync(
    (signal) =>
      Promise.all([api.summary(signal), api.breakdown(signal), api.listSubscriptions({}, signal)]).then(
        ([summary, breakdown, subscriptions]) => ({ summary, breakdown, subscriptions }),
      ),
    [version],
  )
  const upcoming = useAsync((signal) => api.upcoming(period, signal), [period, version])

  const currency = main.data?.summary.currency ?? user?.defaultCurrency ?? 'USD'
  const money = (value: string) => formatMoney(value, currency)
  const [now] = useState(() => new Date())
  const today = useMemo(
    () => new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'long' }).format(now),
    [locale, now],
  )

  const header = (
    <div className="flex shrink-0 items-end justify-between">
      <div>
        <span className="mb-2.5 inline-block rounded-full border border-line px-2.5 py-1 text-[11px] text-muted md:mb-3.5 md:px-3 md:py-[5px] md:text-xs">
          {t.overview.label}
        </span>
        <h1 className="m-0 text-3xl font-light tracking-tight md:text-[40px]">{t.overview.title}</h1>
      </div>
      <span className="hidden text-sm text-muted md:inline">{today}</span>
    </div>
  )

  if (main.loading && !main.data) {
    return (
      <>
        {header}
        <p role="status" className="text-muted">{t.common.loading}</p>
      </>
    )
  }
  if (main.error || !main.data) {
    return (
      <>
        {header}
        <ErrorBox message={messageFor(main.error, t)} onRetry={main.reload} retry={t.common.retry} />
      </>
    )
  }

  const { summary, breakdown, subscriptions } = main.data
  const activeCount = subscriptions.filter((s) => s.isActive).length
  const pausedCount = subscriptions.length - activeCount

  if (subscriptions.length === 0) {
    return (
      <>
        {header}
        <section className="card flex flex-col items-center gap-3 rounded-3xl px-6 py-14 text-center">
          <h2 className="m-0 text-xl font-normal">{t.overview.emptyTitle}</h2>
          <p className="m-0 text-sm text-muted">{t.overview.emptyText}</p>
          <button
            type="button"
            onClick={() => panel.open(null)}
            className="mt-2 rounded-full bg-accent px-6 py-3 text-sm font-semibold text-accent-text"
          >
            {t.overview.emptyCta}
          </button>
        </section>
      </>
    )
  }

  const segments = toSegments(breakdown.bySubscription, t.overview.others)
  const top = breakdown.bySubscription.slice(0, 5)
  const topMax = top[0]?.monthlyCost ?? '0'

  return (
    <>
      {header}

      {/* totals */}
      <section aria-label={t.overview.title} className="grid shrink-0 grid-cols-2 gap-3 md:grid-cols-3 md:gap-5">
        <div className="card col-span-2 rounded-[22px] px-[22px] py-5 md:col-span-1 md:rounded-3xl md:px-7 md:py-[26px]">
          <div className="text-[13px] text-muted md:text-sm">{t.overview.kMonth}</div>
          <div data-testid="monthly-total" className="mt-1.5 text-[42px] font-light tracking-tight md:mt-2.5 md:text-[44px]">
            {money(summary.monthlyTotal)}
          </div>
          <div className="mt-0.5 text-xs text-muted md:mt-1.5 md:text-[13px]">{t.overview.kMonthHint(activeCount)}</div>
        </div>
        <div className="card rounded-[22px] px-[18px] py-4 md:rounded-3xl md:px-7 md:py-[26px]">
          <div className="text-xs text-muted md:text-sm">{t.overview.kYear}</div>
          <div data-testid="yearly-total" className="mt-1.5 text-[26px] font-light md:mt-2.5 md:text-[44px] md:tracking-tight">
            {money(summary.yearlyTotal)}
          </div>
          <div className="mt-1.5 hidden text-[13px] text-muted md:block">{t.overview.kYearHint}</div>
        </div>
        <div className="card rounded-[22px] px-[18px] py-4 md:rounded-3xl md:px-7 md:py-[26px]">
          <div className="text-xs text-muted md:text-sm">{t.overview.kActive}</div>
          <div data-testid="active-count" className="mt-1.5 text-[26px] font-light md:mt-2.5 md:text-[44px] md:tracking-tight">
            {activeCount}
          </div>
          <div data-testid="paused-hint" className="mt-1.5 text-xs text-muted md:text-[13px]">{t.overview.kPaused(pausedCount)}</div>
        </div>
      </section>

      {/* charts */}
      <section className="grid shrink-0 gap-3 md:grid-cols-[1.15fr_1fr] md:gap-5">
        <div className="card flex flex-col items-center gap-5 rounded-[22px] p-5 sm:flex-row md:gap-7 md:rounded-3xl md:p-7">
          <Donut segments={segments} centerLabel={t.overview.perMonth} centerValue={money(breakdown.monthlyTotal)} />
          <div className="min-w-0 flex-1 self-stretch">
            <h2 className="m-0 mb-1 text-base font-normal md:text-lg">{t.overview.donutTitle}</h2>
            <p className="m-0 mb-4 text-[13px] text-muted">{t.overview.donutSub}</p>
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {segments.map((segment, index) => (
                <li key={`${segment.name}-${index}`} className="flex items-center gap-2.5 text-sm">
                  <span className="size-2.5 shrink-0 rounded-[3px]" style={{ background: colorAt(index) }} />
                  <span className="min-w-0 flex-1 truncate">{segment.name}</span>
                  <span className="text-muted">{segment.share}%</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="card rounded-[22px] p-5 md:rounded-3xl md:p-7">
          <h2 className="m-0 mb-1 text-base font-normal md:text-lg">{t.overview.topTitle}</h2>
          <p className="m-0 mb-5 text-[13px] text-muted">{t.overview.topSub}</p>
          <ul className="m-0 flex list-none flex-col gap-4 p-0">
            {top.map((item) => (
              <li key={item.id}>
                <div className="mb-1.5 flex justify-between text-sm">
                  <span>{item.name}</span>
                  <span className="text-muted">{money(item.monthlyCost)}</span>
                </div>
                <div className="h-2 rounded-full bg-line">
                  <div
                    className="h-2 rounded-full bg-accent"
                    style={{ width: `${shareOfMax(item.monthlyCost, topMax)}%` }}
                    data-testid="top-bar"
                  />
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* upcoming */}
      <section className="card shrink-0 rounded-[22px] p-5 md:rounded-3xl md:px-7 md:py-[26px]">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="m-0 text-base font-normal md:text-lg">{t.overview.upTitle}</h2>
          <div role="group" aria-label={t.overview.period} className="flex rounded-full border border-line bg-bg p-[3px] text-[13px]">
            {([7, 30] as const).map((days) => (
              <button
                key={days}
                type="button"
                aria-pressed={period === days}
                onClick={() => setPeriod(days)}
                className={`rounded-full px-3 py-1.5 ${period === days ? 'bg-surface2 text-text' : 'text-muted'}`}
              >
                {days === 7 ? t.overview.d7 : t.overview.d30}
              </button>
            ))}
          </div>
        </div>
        {upcoming.error ? (
          <ErrorBox message={messageFor(upcoming.error, t)} onRetry={upcoming.reload} retry={t.common.retry} />
        ) : upcoming.loading && !upcoming.data ? (
          <p role="status" className="m-0 text-muted">{t.common.loading}</p>
        ) : upcoming.data && upcoming.data.length === 0 ? (
          <p className="m-0 text-sm text-muted">{t.overview.nothingUpcoming}</p>
        ) : (
          <ul className="m-0 grid list-none grid-cols-1 gap-3.5 p-0 sm:grid-cols-2 lg:grid-cols-5">
            {upcoming.data?.map((item) => (
              <li key={`${item.id}-${item.chargeDate}`} className="min-w-0 rounded-[18px] border border-line bg-bg p-4">
                <div className={`text-xs font-medium ${item.daysUntil <= 2 ? 'text-accent' : 'text-muted'}`}>
                  {t.subs.when(item.daysUntil)}
                </div>
                <div className="mt-2 truncate text-[15px]">{item.name}</div>
                <div className="mt-2 flex justify-between text-[13px] text-muted">
                  <span>{formatDay(item.chargeDate, locale)}</span>
                  <span className="text-text">{money(item.amount)}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}

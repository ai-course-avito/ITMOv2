import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/endpoints'
import { messageFor } from '../api/errors'
import type { BillingCycle, ListParams, SortField, SubscriptionListItem } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { useDataVersion } from '../components/DataVersion'
import { Chevron, GridIcon, ListIcon, Search } from '../components/Icons'
import { SubscriptionItem } from '../components/SubscriptionItem'
import { usePanel } from '../components/panelContext'
import { useAsync } from '../components/useAsync'
import { useI18n } from '../i18n'
import { groupByCharge } from '../lib/groups'
import { readStored, writeStored } from '../lib/storage'

type Status = 'all' | 'active' | 'paused'
type View = 'list' | 'cards'

const VIEW_KEY = 'subtracker.view'
const SORTS: SortField[] = ['charge_date', 'monthly_cost', 'amount', 'name']
const CYCLES: BillingCycle[] = ['monthly', 'yearly', 'weekly', 'custom_days']
const ORDER: Record<SortField, 'asc' | 'desc'> = {
  charge_date: 'asc',
  name: 'asc',
  amount: 'desc',
  monthly_cost: 'desc',
}

function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return debounced
}

const chip = (selected: boolean) =>
  `whitespace-nowrap rounded-full px-4 py-2 text-[13px] ${selected ? 'bg-text font-medium text-bg' : 'border border-line text-muted'}`

export default function Subscriptions() {
  const { t } = useI18n()
  const { user } = useAuth()
  const { version, bump } = useDataVersion()
  const panel = usePanel()

  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<Status>('all')
  const [cycle, setCycle] = useState<BillingCycle | null>(null)
  const [sort, setSort] = useState<SortField>('charge_date')
  const [view, setView] = useState<View>(() => (readStored(VIEW_KEY) === 'cards' ? 'cards' : 'list'))
  const [toDelete, setToDelete] = useState<SubscriptionListItem | null>(null)
  const [actionError, setActionError] = useState('')

  const q = useDebounced(search, 300)
  const params = useMemo<ListParams>(
    () => ({
      q,
      sort,
      order: ORDER[sort],
      isActive: status === 'all' ? undefined : status === 'active',
      billingCycle: cycle ?? undefined,
    }),
    [q, sort, status, cycle],
  )

  const list = useAsync((signal) => api.listSubscriptions(params, signal), [params, version])
  const currency = user?.defaultCurrency ?? 'USD'
  const items = useMemo(() => list.data ?? [], [list.data])
  const groups = useMemo(() => groupByCharge(items), [items])
  const filtered = Boolean(q.trim()) || status !== 'all' || cycle !== null

  function chooseView(next: View) {
    setView(next)
    writeStored(VIEW_KEY, next)
  }

  async function toggle(item: SubscriptionListItem) {
    setActionError('')
    try {
      await api.updateSubscription(item.id, { isActive: !item.isActive })
      bump()
    } catch (error) {
      setActionError(messageFor(error, t))
    }
  }

  async function confirmDelete() {
    if (!toDelete) return
    const target = toDelete
    setToDelete(null)
    setActionError('')
    try {
      await api.deleteSubscription(target.id)
      bump()
    } catch (error) {
      setActionError(messageFor(error, t))
    }
  }

  const actions = {
    onEdit: (item: SubscriptionListItem) => panel.open(item),
    onToggle: toggle,
    onDelete: (item: SubscriptionListItem) => setToDelete(item),
  }

  return (
    <>
      <div className="flex shrink-0 items-end justify-between">
        <div>
          <span className="mb-2.5 inline-block rounded-full border border-line px-2.5 py-1 text-[11px] text-muted md:mb-3.5 md:px-3 md:py-[5px] md:text-xs">
            {t.subs.label}
          </span>
          <h1 className="m-0 text-3xl font-light tracking-tight md:text-[40px]">{t.subs.title}</h1>
        </div>
        {list.data && (
          <span className="hidden text-sm text-muted md:inline">
            {t.subs.count(items.length, items.filter((i) => i.isActive).length)}
          </span>
        )}
      </div>

      {/* toolbar */}
      <div className="flex shrink-0 flex-col gap-3.5">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-[18px] -translate-y-1/2 text-muted" />
            <input
              type="search"
              aria-label={t.subs.search}
              placeholder={t.subs.searchPlaceholder}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              maxLength={100}
              className="h-12 w-full rounded-full border border-line bg-surface pr-5 pl-12 text-sm text-text outline-none focus:border-accent md:h-[50px]"
            />
          </div>
          <label className="relative hidden items-center md:flex">
            <span className="sr-only">{t.subs.sortLabel}</span>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as SortField)}
              className="h-[50px] appearance-none rounded-full border border-line bg-surface pr-10 pl-5 text-sm text-text"
            >
              {SORTS.map((s) => (
                <option key={s} value={s}>
                  {t.subs.sortLabel}: {t.subs.sort[s]}
                </option>
              ))}
            </select>
            <Chevron size={14} className="pointer-events-none absolute right-4" />
          </label>
          <div role="group" aria-label={t.subs.view} className="flex rounded-full border border-line bg-surface p-1">
            {(
              [
                ['list', t.subs.viewList, <ListIcon key="l" />],
                ['cards', t.subs.viewCards, <GridIcon key="c" />],
              ] as const
            ).map(([value, label, icon]) => (
              <button
                key={value}
                type="button"
                aria-label={label}
                aria-pressed={view === value}
                onClick={() => chooseView(value)}
                className={`flex h-10 w-[42px] items-center justify-center rounded-full ${view === value ? 'bg-surface2 text-text' : 'text-muted'}`}
              >
                {icon}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2.5 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {(['all', 'active', 'paused'] as const).map((value) => (
            <button key={value} type="button" aria-pressed={status === value} onClick={() => setStatus(value)} className={chip(status === value)}>
              {value === 'all' ? t.subs.filterAll : value === 'active' ? t.subs.filterActive : t.subs.filterPaused}
            </button>
          ))}
          <span aria-hidden="true" className="mx-1.5 hidden h-[22px] w-px bg-line md:block" />
          <span className="hidden text-[13px] text-muted md:inline">{t.subs.cycleLabel}:</span>
          {CYCLES.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={cycle === value}
              onClick={() => setCycle(cycle === value ? null : value)}
              className={chip(cycle === value)}
            >
              {t.subs.cycle[value]}
            </button>
          ))}
        </div>
      </div>

      {actionError && <p role="alert" className="m-0 text-sm text-red-400">{actionError}</p>}

      {list.error ? (
        <div role="alert" className="card rounded-3xl p-8 text-center">
          <p className="mb-4 text-muted">{messageFor(list.error, t)}</p>
          <button type="button" onClick={list.reload} className="rounded-full bg-accent px-6 py-3 text-sm font-semibold text-accent-text">
            {t.common.retry}
          </button>
        </div>
      ) : list.loading && !list.data ? (
        <p role="status" className="m-0 text-muted">{t.common.loading}</p>
      ) : items.length === 0 ? (
        <div className="card flex flex-col items-center gap-3 rounded-3xl px-6 py-14 text-center">
          <h2 className="m-0 text-xl font-normal">{filtered ? t.subs.nothingFound : t.subs.emptyTitle}</h2>
          {!filtered && (
            <>
              <p className="m-0 text-sm text-muted">{t.subs.emptyText}</p>
              <button
                type="button"
                onClick={() => panel.open(null)}
                className="mt-2 rounded-full bg-accent px-6 py-3 text-sm font-semibold text-accent-text"
              >
                {t.overview.emptyCta}
              </button>
            </>
          )}
        </div>
      ) : (
        <div className={view === 'list' ? 'card rounded-[22px] md:rounded-3xl' : 'flex flex-col gap-5'}>
          {groups.map((group, groupIndex) => (
            <section key={group.key} aria-label={t.subs.groups[group.key]} data-testid={`group-${group.key}`}>
              <div
                className={`flex items-center justify-between text-[11px] text-muted md:text-[13px] ${
                  view === 'list'
                    ? `bg-bg px-[18px] pt-3 pb-2 md:px-7 md:pt-4 md:pb-2.5 ${groupIndex === 0 ? 'rounded-t-[21px] md:rounded-t-[23px]' : 'border-t border-line'}`
                    : 'mb-3'
                }`}
              >
                <h2 className="m-0 text-[11px] font-semibold tracking-wider uppercase md:text-xs">
                  {t.subs.groups[group.key]}
                </h2>
                <span>{t.subs.groupCount(group.items.length)}</span>
              </div>
              <ul className={view === 'list' ? 'm-0 list-none p-0' : 'm-0 grid list-none grid-cols-1 gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3'}>
                {group.items.map((item) => (
                  <SubscriptionItem key={item.id} item={item} currency={currency} view={view} {...actions} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      {toDelete && (
        <ConfirmDialog
          title={t.subs.deleteTitle}
          text={t.subs.deleteText(toDelete.name)}
          confirmLabel={t.common.delete}
          onConfirm={confirmDelete}
          onCancel={() => setToDelete(null)}
        />
      )}
    </>
  )
}

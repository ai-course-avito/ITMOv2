import type { SubscriptionListItem } from '../api/types'
import { useI18n } from '../i18n'
import { formatDay, formatShortDay } from '../lib/dates'
import { formatMoney } from '../lib/money'
import { colorAt } from '../lib/palette'
import { ActionsMenu } from './ActionsMenu'

export interface ItemActions {
  onEdit: (item: SubscriptionListItem) => void
  onToggle: (item: SubscriptionListItem) => void
  onDelete: (item: SubscriptionListItem) => void
}

interface Props extends ItemActions {
  item: SubscriptionListItem
  currency: string
  view: 'list' | 'cards'
}

function useLabels(item: SubscriptionListItem, currency: string) {
  const { t, locale } = useI18n()
  const per =
    item.billingCycle === 'custom_days'
      ? t.subs.per.custom(item.customIntervalDays ?? 0)
      : t.subs.per[item.billingCycle]
  return {
    t,
    billed: `${formatMoney(item.amount, currency)} ${per}`,
    monthly: formatMoney(item.monthlyCost, currency),
    when: item.daysUntil === null ? t.subs.notCharged : t.subs.when(item.daysUntil),
    date: item.chargeDate ? formatDay(item.chargeDate, locale, true) : '—',
    shortDate: item.chargeDate ? formatShortDay(item.chargeDate, locale) : '',
    soon: item.daysUntil !== null && item.daysUntil <= 2,
  }
}

function Avatar({ item, size }: { item: SubscriptionListItem; size: string }) {
  return (
    <div
      aria-hidden="true"
      className={`flex shrink-0 items-center justify-center font-semibold text-[#14100c] ${size}`}
      style={{ background: item.isActive ? colorAt(item.id) : '#8d8d89' }}
    >
      {item.name.trim().charAt(0).toUpperCase()}
    </div>
  )
}

export function SubscriptionItem({ item, currency, view, onEdit, onToggle, onDelete }: Props) {
  const l = useLabels(item, currency)
  const menu = (
    <ActionsMenu
      name={item.name}
      isActive={item.isActive}
      onEdit={() => onEdit(item)}
      onToggle={() => onToggle(item)}
      onDelete={() => onDelete(item)}
    />
  )

  if (view === 'cards') {
    return (
      <li
        data-testid="subscription-item"
        className={`card rounded-[22px] p-5 ${item.isActive ? '' : 'opacity-55'}`}
      >
        <div className="flex items-start gap-3">
          <Avatar item={item} size="size-11 rounded-[14px] text-[17px]" />
          <div className="min-w-0 flex-1">
            <div className="truncate text-base">{item.name}</div>
            {item.note && <div className="mt-1 truncate text-xs text-muted">{item.note}</div>}
          </div>
          {menu}
        </div>
        <div className="mt-5 flex items-end justify-between">
          <div>
            <div className={`text-xs ${l.soon ? 'text-accent' : 'text-muted'}`}>{l.when}</div>
            <div className="mt-1 text-sm">{l.date}</div>
          </div>
          <div className="text-right">
            <div className="text-lg font-medium">{l.monthly}</div>
            <div className="mt-0.5 text-[11px] text-muted">{l.t.subs.perMonth}</div>
          </div>
        </div>
        <div className="mt-3 text-xs text-muted">{l.billed}</div>
      </li>
    )
  }

  return (
    <li
      data-testid="subscription-item"
      className={`flex items-center gap-3 border-t border-line px-[18px] py-[13px] md:gap-[18px] md:px-7 md:py-4 ${item.isActive ? '' : 'opacity-55'}`}
    >
      <Avatar item={item} size="size-10 rounded-[13px] text-base md:size-11 md:rounded-[14px] md:text-[17px]" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[15px] md:text-base">{item.name}</div>
        {item.note && <div className="mt-1 hidden truncate text-xs text-muted md:block">{item.note}</div>}
        <div className={`mt-[3px] text-xs md:hidden ${l.soon ? 'text-accent' : 'text-muted'}`}>
          {l.when}
          {l.shortDate && ` · ${l.shortDate}`}
        </div>
      </div>
      <div className="hidden w-[200px] md:block">
        <div className="text-sm">{l.date}</div>
        <div className={`mt-1 text-xs ${l.soon ? 'text-accent' : 'text-muted'}`}>{l.when}</div>
      </div>
      <div className="hidden w-[170px] text-sm text-muted md:block">{l.billed}</div>
      <div className="shrink-0 text-right md:w-[110px]">
        <div className="text-[15px] font-medium md:text-[17px]">{l.monthly}</div>
        <div className="mt-[3px] hidden text-[11px] font-normal text-muted md:block">{l.t.subs.perMonth}</div>
        <div className="mt-[3px] text-[11px] text-muted md:hidden">{l.billed}</div>
      </div>
      {menu}
    </li>
  )
}

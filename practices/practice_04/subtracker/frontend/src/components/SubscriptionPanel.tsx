import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { api } from '../api/endpoints'
import { fieldErrors, messageFor } from '../api/errors'
import type { BillingCycle, Subscription, SubscriptionInput } from '../api/types'
import { useI18n } from '../i18n'
import { isValidAmount, normalizeAmount } from '../lib/money'
import { todayIso } from '../lib/dates'
import { Close } from './Icons'

const SHOWN_FIELDS = ['name', 'amount', 'startDate', 'customIntervalDays', 'note']
const CYCLES: BillingCycle[] = ['monthly', 'yearly', 'weekly', 'custom_days']

interface Props {
  // null = new subscription
  subscription: Subscription | null
  onClose: () => void
  onSaved: () => void
}

type Errors = Partial<Record<keyof SubscriptionInput, string>>

export function SubscriptionPanel({ subscription, onClose, onSaved }: Props) {
  const { t } = useI18n()
  const ids = { name: useId(), amount: useId(), start: useId(), days: useId(), note: useId() }
  const titleId = useId()
  const nameRef = useRef<HTMLInputElement>(null)
  const openerRef = useRef<Element | null>(document.activeElement)

  const [name, setName] = useState(subscription?.name ?? '')
  const [amount, setAmount] = useState(subscription?.amount ?? '')
  const [startDate, setStartDate] = useState(subscription?.startDate ?? todayIso())
  const [cycle, setCycle] = useState<BillingCycle>(subscription?.billingCycle ?? 'monthly')
  const [days, setDays] = useState(subscription?.customIntervalDays?.toString() ?? '')
  const [note, setNote] = useState(subscription?.note ?? '')
  const [active, setActive] = useState(subscription?.isActive ?? true)
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    nameRef.current?.focus()
    const opener = openerRef.current
    return () => {
      if (opener instanceof HTMLElement) opener.focus()
    }
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  function validate(): Errors {
    const next: Errors = {}
    const trimmed = name.trim()
    if (!trimmed || trimmed.length > 255) next.name = t.form.errName
    if (!isValidAmount(amount)) next.amount = t.form.errAmount
    if (!startDate) next.startDate = t.form.errDate
    if (cycle === 'custom_days') {
      const n = Number(days)
      if (!Number.isInteger(n) || n < 1 || n > 3650) next.customIntervalDays = t.form.errDays
    }
    if (note.length > 500) next.note = t.form.errNote
    return next
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const found = validate()
    setErrors(found)
    setFormError('')
    if (Object.keys(found).length > 0) return

    const input: SubscriptionInput = {
      name: name.trim(),
      amount: normalizeAmount(amount),
      billingCycle: cycle,
      customIntervalDays: cycle === 'custom_days' ? Number(days) : null,
      startDate,
      note: note.trim() || null,
      isActive: active,
    }
    setSaving(true)
    try {
      if (subscription) await api.updateSubscription(subscription.id, input)
      else await api.createSubscription(input)
      onSaved()
    } catch (error) {
      const shown = Object.keys(fieldErrors(error)).filter((key) => SHOWN_FIELDS.includes(key))
      if (shown.length > 0) {
        setErrors(Object.fromEntries(shown.map((key) => [key, t.form.errServer])) as Errors)
      } else {
        setFormError(messageFor(error, t))
      }
    } finally {
      setSaving(false)
    }
  }

  const inputClass = (error?: string) =>
    `h-[50px] w-full rounded-[14px] border bg-bg px-4 text-[15px] text-text outline-none focus:border-accent ${error ? 'border-red-400' : 'border-line'}`

  return (
    <div className="fixed inset-0 z-40" data-testid="subscription-panel">
      <div className="absolute inset-0 bg-black/55" onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="absolute inset-x-0 bottom-0 flex max-h-[92vh] flex-col overflow-y-auto rounded-t-[28px] border border-line bg-surface p-6 md:inset-y-0 md:right-0 md:left-auto md:max-h-none md:w-[480px] md:rounded-none md:border-y-0 md:border-r-0 md:px-9 md:py-8"
      >
        <form onSubmit={submit} noValidate className="flex flex-1 flex-col gap-5">
          <div className="flex items-start justify-between">
            <div>
              <span className="mb-3 inline-block rounded-full border border-line px-3 py-1 text-xs text-muted">
                {subscription ? t.form.editBadge : t.form.newBadge}
              </span>
              <h2 id={titleId} className="m-0 text-[28px] font-light tracking-tight">
                {subscription ? t.form.editTitle : t.form.newTitle}
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t.common.close}
              className="flex size-10 items-center justify-center rounded-full border border-line bg-bg text-text"
            >
              <Close size={16} />
            </button>
          </div>

          <div>
            <label htmlFor={ids.name} className="mb-2 block text-[13px] text-muted">{t.form.name}</label>
            <input
              id={ids.name}
              ref={nameRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={255}
              aria-invalid={Boolean(errors.name)}
              className={inputClass(errors.name)}
            />
            {errors.name && <p role="alert" className="mt-1.5 text-xs text-red-400">{errors.name}</p>}
          </div>

          <div className="flex gap-3.5">
            <div className="flex-1">
              <label htmlFor={ids.amount} className="mb-2 block text-[13px] text-muted">{t.form.amount}</label>
              <input
                id={ids.amount}
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                aria-invalid={Boolean(errors.amount)}
                className={inputClass(errors.amount)}
              />
              {errors.amount && <p role="alert" className="mt-1.5 text-xs text-red-400">{errors.amount}</p>}
            </div>
            <div className="flex-1">
              <label htmlFor={ids.start} className="mb-2 block text-[13px] text-muted">{t.form.startDate}</label>
              <input
                id={ids.start}
                type="date"
                value={startDate}
                min="2000-01-01"
                max="2100-12-31"
                onChange={(e) => setStartDate(e.target.value)}
                aria-invalid={Boolean(errors.startDate)}
                className={inputClass(errors.startDate)}
              />
              {errors.startDate && <p role="alert" className="mt-1.5 text-xs text-red-400">{errors.startDate}</p>}
            </div>
          </div>

          <fieldset className="m-0 border-0 p-0">
            <legend className="mb-2 p-0 text-[13px] text-muted">{t.form.cycle}</legend>
            <div className="flex rounded-full border border-line bg-bg p-1">
              {CYCLES.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setCycle(value)}
                  aria-pressed={cycle === value}
                  className={`flex-1 rounded-full py-2.5 text-sm ${cycle === value ? 'bg-accent font-medium text-accent-text' : 'text-muted'}`}
                >
                  {value === 'custom_days' ? t.form.cycleCustom : t.subs.cycle[value]}
                </button>
              ))}
            </div>
          </fieldset>

          {cycle === 'custom_days' && (
            <div>
              <label htmlFor={ids.days} className="mb-2 block text-[13px] text-muted">
                {t.form.customDays} <span className="opacity-70">({t.form.customHint})</span>
              </label>
              <input
                id={ids.days}
                inputMode="numeric"
                value={days}
                onChange={(e) => setDays(e.target.value)}
                aria-invalid={Boolean(errors.customIntervalDays)}
                className={inputClass(errors.customIntervalDays)}
              />
              {errors.customIntervalDays && (
                <p role="alert" className="mt-1.5 text-xs text-red-400">{errors.customIntervalDays}</p>
              )}
            </div>
          )}

          <div className="flex items-center justify-between rounded-2xl border border-line bg-bg px-4 py-3.5 text-sm">
            <span className="text-muted">{t.form.nextCharge}</span>
            <span className="font-medium">
              {subscription ? subscription.nextBillingDate : <span className="font-normal text-muted">{t.form.nextAuto}</span>}
            </span>
          </div>

          <div>
            <label htmlFor={ids.note} className="mb-2 block text-[13px] text-muted">
              {t.form.note} <span className="opacity-70">({t.form.optional})</span>
            </label>
            <input
              id={ids.note}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              aria-invalid={Boolean(errors.note)}
              className={inputClass(errors.note)}
            />
            {errors.note && <p role="alert" className="mt-1.5 text-xs text-red-400">{errors.note}</p>}
          </div>

          <label className="flex cursor-pointer items-center justify-between text-sm">
            <span>{t.form.active}</span>
            <input
              type="checkbox"
              role="switch"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
              className="peer sr-only"
            />
            <span
              aria-hidden="true"
              className={`relative h-[26px] w-[46px] rounded-full transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent ${active ? 'bg-accent' : 'bg-line'}`}
            >
              <span
                className={`absolute top-[3px] size-5 rounded-full bg-accent-text transition-all ${active ? 'right-[3px]' : 'left-[3px] bg-muted'}`}
              />
            </span>
          </label>

          {formError && <p role="alert" className="text-sm text-red-400">{formError}</p>}

          <div className="mt-auto flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="h-[52px] flex-1 rounded-full border border-line bg-transparent text-[15px] text-text"
            >
              {t.common.cancel}
            </button>
            <button
              type="submit"
              disabled={saving}
              className="h-[52px] flex-[2] rounded-full bg-accent text-[15px] font-semibold text-accent-text disabled:opacity-60"
            >
              {saving ? t.form.saving : t.common.save}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

import { cloneElement, isValidElement, useId, useState, type ComponentType, type MouseEvent, type ReactElement, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRightIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Combobox, ComboboxContent, ComboboxEmpty, ComboboxInput, ComboboxItem, ComboboxList, ComboboxTrigger } from '@/components/ui/combobox'
import { Field, FieldContent, FieldDescription, FieldError, FieldLabel } from '@/components/ui/field'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { parseJsonObject, pretty } from '@/lib/format'
import { t } from '@/lib/i18n'
import { cn } from '@/lib/utils'

interface FormFieldProps {
  label: string
  description?: ReactNode
  error?: ReactNode
  className?: string
  /** One control that accepts `id` (Input, Textarea, OptionSelect, JsonEditor …). */
  children: ReactNode
}

/** A labelled control: the shadcn Field, with the label tied to the control (and named as a group). */
export function FormField({ label, description, error, className, children }: FormFieldProps) {
  const id = useId()
  const control = isValidElement(children) ? cloneElement(children as ReactElement<{ id?: string }>, { id }) : children
  return (
    <Field aria-labelledby={`${id}-label`} data-invalid={error ? true : undefined} className={className}>
      <FieldLabel id={`${id}-label`} htmlFor={id}>
        {label}
      </FieldLabel>
      {control}
      {description && <FieldDescription>{description}</FieldDescription>}
      {error && <FieldError>{error}</FieldError>}
    </Field>
  )
}

interface ToggleFieldProps {
  label: string
  description?: ReactNode
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  disabled?: boolean
}

/** A setting that is on or off: label and help on the left, the switch on the right. */
export function SwitchField({ label, description, checked, onCheckedChange, disabled }: ToggleFieldProps) {
  const id = useId()
  return (
    <Field orientation="horizontal" data-disabled={disabled ? true : undefined}>
      <FieldContent>
        <FieldLabel htmlFor={id}>{label}</FieldLabel>
        {description && <FieldDescription>{description}</FieldDescription>}
      </FieldContent>
      <Switch id={id} aria-label={label} checked={checked} onCheckedChange={onCheckedChange} disabled={disabled} />
    </Field>
  )
}

/** A checkbox with its label (and help) beside it. */
export function CheckboxField({ label, description, checked, onCheckedChange, disabled }: ToggleFieldProps) {
  const id = useId()
  return (
    <Field orientation="horizontal" data-disabled={disabled ? true : undefined}>
      <Checkbox id={id} aria-label={label} checked={checked} onCheckedChange={(v) => onCheckedChange(!!v)} disabled={disabled} />
      <FieldContent>
        <FieldLabel htmlFor={id} className="font-normal">
          {label}
        </FieldLabel>
        {description && <FieldDescription>{description}</FieldDescription>}
      </FieldContent>
    </Field>
  )
}

type IconType = ComponentType<{ className?: string }>

/** Something that belongs to an entity: a related entity (a link) or a plain fact. */
export interface OptionAttr {
  text: string
  /** Where it leads: the related entity's page. Without it the attribute is just a fact. */
  to?: string
  icon?: IconType
  mono?: boolean
  /** A long text: it gets a row of its own and wraps over up to two lines instead of being cut to one. */
  wide?: boolean
}

/** An entity in a picker: what its card shows. */
export interface Option {
  value: string
  /** The title. */
  label: string
  id?: string
  icon?: IconType
  /** A line under the title (simple choices: what each one means). */
  description?: string
  /** The entity's own page. */
  to?: string
  attrs?: OptionAttr[]
}

// a link inside a card must neither pick the card nor close the list before it navigates
const keepOut = { onClick: (e: MouseEvent) => e.stopPropagation(), onPointerDown: (e: MouseEvent) => e.stopPropagation(), onMouseDown: (e: MouseEvent) => e.stopPropagation() }

const chip = 'inline-flex min-w-0 max-w-full items-center gap-1 rounded-md border bg-background px-1.5 py-0.5 text-xs text-muted-foreground'
const wideChip = 'w-full items-start'

/** One fact or link of an entity, as a small chip. */
export function AttrChip({ attr }: { attr: OptionAttr }) {
  const Icon = attr.icon
  const body = (
    <>
      {Icon && <Icon className={cn('size-3 shrink-0', attr.wide && 'mt-0.5')} />}
      <span title={attr.text} className={cn(attr.wide ? 'line-clamp-2 [overflow-wrap:anywhere]' : 'truncate', attr.mono && 'value-mono')}>
        {attr.text}
      </span>
    </>
  )
  return attr.to ? (
    <Link to={attr.to} {...keepOut} className={cn(chip, attr.wide && wideChip, 'transition-colors hover:border-foreground/30 hover:text-foreground')}>
      {body}
    </Link>
  ) : (
    <span className={cn(chip, attr.wide && wideChip)}>{body}</span>
  )
}

function IdBadge({ id }: { id: string }) {
  return <span className="value-mono shrink-0 rounded-md border bg-muted px-1.5 py-0.5 text-muted-foreground">{id}</span>
}

function IconTile({ icon: Icon, small }: { icon?: IconType; small?: boolean }) {
  if (!Icon) return null
  return (
    <span className={cn('grid shrink-0 place-items-center rounded-lg border bg-muted text-muted-foreground', small ? 'size-7 [&_svg]:size-3.5' : 'size-9 [&_svg]:size-4')}>
      <Icon />
    </span>
  )
}

/**
 * An entity as a card: its icon, title and id, and below them what belongs to it, as links to the
 * related entities. `compact` is the small form kept in a field once the entity is chosen.
 */
export function OptionCard({ option, compact }: { option: Option; compact?: boolean }) {
  return (
    <span className="flex min-w-0 flex-1 items-center gap-3">
      <IconTile icon={option.icon} small={compact} />
      <span className="grid min-w-0 flex-1 gap-1">
        <span className="truncate text-sm font-medium">{option.label}</span>
        {!compact && option.attrs && option.attrs.length > 0 && (
          <span className="flex max-h-[4rem] min-w-0 flex-wrap gap-1 overflow-hidden">
            {option.attrs.map((a, i) => (
              <AttrChip key={i} attr={a} />
            ))}
          </span>
        )}
      </span>
      {option.id && <IdBadge id={option.id} />}
      {!compact && option.to && (
        <Link to={option.to} {...keepOut} aria-label={t('Open {name}', { name: option.label })}className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-background hover:text-foreground">
          <ArrowUpRightIcon className="size-4" />
        </Link>
      )}
    </span>
  )
}

/** Every card in a picker is this tall (title row, a two-line text, a row of chips, padding), so the list can be sized in cards. */
const CARD_HEIGHT = 'h-28'

/** The classes that make a combobox item a card (the picker's list is a list of cards). */
export const cardItem = `${CARD_HEIGHT} shrink-0 items-center rounded-lg border border-transparent p-2 pr-9 data-highlighted:border-border data-highlighted:bg-muted`

/** The list of cards shows five whole cards (5 x 7rem + the list's 0.5rem padding) and scrolls beyond that; a short window shrinks it. */
export const cardList = 'max-h-[min(35.5rem,calc(var(--available-height)-3.5rem))]'

/** The words a card can be found by: its id, title and what belongs to it. */
const searchText = (o: Option) => [o.id, o.label, ...(o.attrs ?? []).map((a) => a.text)].filter(Boolean).join(' ').toLowerCase()

interface OptionPickerProps {
  id?: string
  value: string | null
  onChange: (value: string) => void
  options: Option[]
  placeholder?: string
  className?: string
  disabled?: boolean
}

/** A simple card: an icon and a name, and under it what the choice means. */
function ChoiceCard({ option, compact }: { option: Option; compact?: boolean }) {
  return (
    <span className="flex min-w-0 flex-1 items-center gap-3">
      <IconTile icon={option.icon} small={compact} />
      <span className="grid min-w-0 flex-1 gap-0.5 text-left">
        <span className="truncate text-sm font-medium">{option.label}</span>
        {!compact && option.description && <span className="text-xs whitespace-normal text-muted-foreground">{option.description}</span>}
      </span>
    </span>
  )
}

/**
 * A short list of choices (an enum), as a list of simple cards: an icon, a name and what it means. Like the pickers of
 * entities, but with nothing to search or open. Base UI shows the raw value unless the options are passed as `items`.
 */
export function OptionSelect({ id, value, onChange, options, placeholder = t('Select…'), className, disabled }: OptionPickerProps) {
  return (
    <Select value={value} onValueChange={(v) => v !== null && onChange(v)} items={options} disabled={disabled}>
      <SelectTrigger id={id} className={cn('h-auto min-h-10 w-full py-1.5', className)}>
        <SelectValue placeholder={placeholder}>
          {(v: string | null) => {
            const chosen = options.find((o) => o.value === v)
            return chosen ? <ChoiceCard option={chosen} compact /> : placeholder
          }}
        </SelectValue>
      </SelectTrigger>
      <SelectContent alignItemWithTrigger={false} className="p-1.5">
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value} className="my-1 h-auto items-center rounded-lg border border-transparent p-2 pr-9 focus:border-border focus:bg-muted">
            <ChoiceCard option={o} />
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

/**
 * Choosing an entity (agent, model, server, unit …). The list is a list of cards with a search on top;
 * once one is chosen the field keeps a small card of it, with a link to open it.
 */
export function OptionCombobox({ id, value, onChange, options, placeholder = t('Select…'), className, disabled }: OptionPickerProps) {
  const selected = options.find((o) => o.value === value) ?? null
  const [query, setQuery] = useState('')
  return (
    <Combobox
      items={options}
      value={selected}
      onValueChange={(o: Option | null) => o && onChange(o.value)}
      itemToStringLabel={(o: Option) => o.label}
      filter={(o: Option, q: string) => searchText(o).includes(q.trim().toLowerCase())}
      inputValue={query}
      onInputValueChange={(v: string) => setQuery(v)}
      onOpenChange={(open: boolean) => !open && setQuery('')}
      disabled={disabled}
    >
      <div className={cn('flex w-full items-center rounded-lg border bg-background has-[:focus-visible]:border-ring has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50', disabled && 'opacity-50', className)}>
        <ComboboxTrigger id={id} disabled={disabled} className="flex min-h-10 min-w-0 flex-1 items-center gap-2 rounded-lg p-1.5 text-left outline-none">
          {selected ? <OptionCard option={selected} compact /> : <span className="flex-1 px-1 text-sm text-muted-foreground">{placeholder}</span>}
        </ComboboxTrigger>
        {selected?.to && (
          <Link to={selected.to} aria-label={t('Open {name}', { name: selected.label })}className="mr-1 grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
            <ArrowUpRightIcon className="size-4" />
          </Link>
        )}
      </div>
      <ComboboxContent className="min-w-[22rem]">
        <ComboboxInput showTrigger={false} placeholder={t('Search…')} />
        <ComboboxEmpty>{t('Nothing found.')}</ComboboxEmpty>
        <ComboboxList className={cardList}>
          {(o: Option) => (
            <ComboboxItem key={o.value} value={o} className={cardItem}>
              <OptionCard option={o} />
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  )
}

/** A JSON-object textarea with live validation and a Format button. */
export function JsonEditor({
  id,
  value,
  onChange,
  rows = 12,
  placeholder,
}: {
  id?: string
  value: string
  onChange: (v: string) => void
  rows?: number
  placeholder?: string
}) {
  const parsed = parseJsonObject(value)
  return (
    <div className="grid gap-1.5">
      <Textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        spellCheck={false}
        placeholder={placeholder}
        aria-invalid={!parsed.ok}
        className="value-mono"
        style={{ minHeight: `${rows * 1.4 + 1}rem` }} // field-sizing would shrink an empty box to its placeholder; keep the rows asked for
      />
      <div className="flex items-center justify-between gap-2 text-xs">
        {parsed.ok ? <span className="text-muted-foreground">{t('Valid JSON')}</span> : <span className="text-destructive">{parsed.error}</span>}
        <Button type="button" variant="ghost" size="xs" disabled={!parsed.ok} onClick={() => parsed.ok && onChange(pretty(parsed.value))}>
          {t('Format')}
        </Button>
      </div>
    </div>
  )
}

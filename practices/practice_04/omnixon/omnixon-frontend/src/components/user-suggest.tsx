import { useQuery } from '@tanstack/react-query'
import { Combobox, ComboboxContent, ComboboxEmpty, ComboboxInput, ComboboxItem, ComboboxList } from '@/components/ui/combobox'
import { OptionCard, cardItem, cardList } from '@/components/form'
import { userOption } from '@/lib/options'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n'
import { useDebounced } from '@/lib/use-debounced'
import type { User } from '@/lib/types'
import { cn } from '@/lib/utils'

export const MIN_SEARCH = 3

/**
 * A box for a user's external id with suggestions from the service (GET /users?query=): users of
 * the agent whose id starts with what is typed, once there are at least 3 characters.
 * Whatever is typed is the value; the suggestions only help. `disabled` mutes it (e.g. until an agent is chosen, because ids differ from agent to agent).
 */
export function UserSuggest({
  id,
  value,
  onChange,
  actAs,
  disabled,
  placeholder = 'telegram-12345', // an example id, as the clients name their users
  disabledPlaceholder,
  className,
}: {
  id?: string
  value: string
  onChange: (value: string) => void
  /** The agent to search in (an admin acting as it); the agent of the token when left out. */
  actAs?: number
  disabled?: boolean
  placeholder?: string
  disabledPlaceholder?: string
  className?: string
}) {
  const typed = value.trim()
  const query = useDebounced(typed)
  const searching = !disabled && query.length >= MIN_SEARCH && typed.length >= MIN_SEARCH
  const found = useQuery({
    queryKey: ['user-search', actAs ?? 'me', query],
    queryFn: () => api.searchUsers(query, 10, actAs),
    enabled: searching,
    staleTime: 30_000,
    retry: false,
  })
  const items: User[] = searching ? (found.data ?? []) : []
  const empty =
    typed.length < MIN_SEARCH
      ? t('Type at least {count} characters to search', { count: MIN_SEARCH })
      : found.isError
        ? t('The search failed')
        : found.isFetching || query !== typed
          ? t('Searching…')
          : t('No users start with “{text}”', { text: typed })

  return (
    <Combobox
      items={items}
      filter={null}
      inputValue={value}
      onInputValueChange={(v: string, details: { reason?: string }) => {
        // what is typed is the value; the box emptying itself when it loses focus is not an edit
        if (v === '' && details?.reason !== 'input-change') return
        onChange(v)
      }}
      onValueChange={(u: User | null) => u && onChange(u.external_id)}
      itemToStringLabel={(u: User) => u.external_id}
      disabled={disabled}
    >
      <ComboboxInput id={id} showTrigger={false} disabled={disabled} placeholder={disabled ? (disabledPlaceholder ?? placeholder) : placeholder} className={cn('w-full', className)} />
      <ComboboxContent className="min-w-[22rem]">
        <ComboboxEmpty>{empty}</ComboboxEmpty>
        <ComboboxList className={cardList}>
          {(u: User) => (
            <ComboboxItem key={u.id} value={u} className={cardItem}>
              <OptionCard option={userOption(u)} />
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  )
}

import { CheckIcon, LanguagesIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { LOCALES, locale, switchLocale, t } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/** The language of the panel, as a menu of the two languages. Choosing one opens the same page under its prefix. */
export function LanguageSwitch({ className }: { className?: string }) {
  const current = LOCALES.find((l) => l.code === locale)
  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant="ghost" size="sm" aria-label={t('Language')} className={className} />}>
        <LanguagesIcon />
        <span>{current?.label}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-36">
        {LOCALES.map((l) => (
          <DropdownMenuItem key={l.code} onClick={() => l.code !== locale && switchLocale(l.code)}>
            <CheckIcon className={cn(l.code !== locale && 'invisible')} />
            {l.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

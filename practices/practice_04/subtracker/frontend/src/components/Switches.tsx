import { useI18n, type Lang } from '../i18n'
import { useTheme } from '../theme/ThemeContext'
import { Moon } from './Icons'

export function LangSwitch() {
  const { lang, setLang, t } = useI18n()
  const item = (code: Lang, label: string) => (
    <button
      type="button"
      onClick={() => setLang(code)}
      aria-pressed={lang === code}
      className={`rounded-full px-3 py-1.5 ${lang === code ? 'bg-accent font-medium text-accent-text' : 'text-muted'}`}
    >
      {label}
    </button>
  )
  return (
    <div
      role="group"
      aria-label={t.nav.language}
      className="flex rounded-full border border-line bg-surface p-[3px] text-[13px]"
    >
      {item('ru', 'RU')}
      {item('en', 'EN')}
    </div>
  )
}

export function ThemeToggle() {
  const { toggleTheme } = useTheme()
  const { t } = useI18n()
  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={t.nav.theme}
      className="flex size-11 items-center justify-center rounded-full border border-line bg-surface text-text md:size-10"
    >
      <Moon />
    </button>
  )
}

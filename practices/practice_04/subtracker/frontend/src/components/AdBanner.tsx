import { useAuth } from '../auth/AuthContext'
import { useT } from '../i18n'

export function AdBanner() {
  const { user } = useAuth()
  const t = useT()
  if (!user || user.plan === 'pro') return null
  return (
    <aside
      aria-label={t.common.ad}
      data-testid="ad-banner"
      className="flex h-[52px] items-center justify-center rounded-2xl border border-dashed border-line px-5 text-xs text-muted md:h-14 md:justify-between md:text-[13px]"
    >
      <span>
        <span className="mr-2 font-semibold tracking-wider md:mr-2.5">{t.common.ad}</span>
        {t.common.adText}
      </span>
      <span className="hidden font-medium text-accent md:inline">{t.common.adCta}</span>
    </aside>
  )
}

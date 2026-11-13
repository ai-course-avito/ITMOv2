import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useTheme } from 'next-themes'
import { KeyRoundIcon, MoonIcon, SunIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Logo } from '@/components/logo'
import { LanguageSwitch } from '@/components/language-switch'
import DotField from '@/components/DotField'
import TechText from '@/components/TechText'
import { FormField } from '@/components/form'
import { Spinner } from '@/components/ui/spinner'
import { FieldGroup } from '@/components/ui/field'
import { session } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { t } from '@/lib/i18n'
import { errorMessage } from '@/lib/queries'

export default function Login() {
  const { login } = useAuth()
  const { resolvedTheme, setTheme } = useTheme()
  const dark = resolvedTheme !== 'light'
  const [token, setToken] = useState('')
  const [baseUrl, setBaseUrl] = useState(session.baseUrl)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(token, baseUrl)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-svh lg:grid-cols-[1.15fr_1fr]">
      {/* hero: the wordmark reacts to the cursor */}
      <div className="relative flex min-h-64 flex-col overflow-hidden bg-sidebar lg:min-h-svh">
        <div aria-hidden className="absolute inset-0">
          <DotField dotRadius={1.5} dotSpacing={16} cursorRadius={380} bulgeStrength={55} gradientFrom={dark ? 'rgba(250,250,250,0.26)' : 'rgba(24,24,27,0.26)'} gradientTo={dark ? 'rgba(250,250,250,0.26)' : 'rgba(24,24,27,0.26)'} glowColor={dark ? 'rgba(250,250,250,0.05)' : 'rgba(24,24,27,0.04)'} />
        </div>
        <div className="relative z-10 flex items-center gap-3 p-6 text-sm text-muted-foreground">
          <Logo className="size-7" /> {t('One API for every model, memory and tool.')}
        </div>
        <div className="relative z-10 flex-1">
          <TechText
            key={dark ? 'dark' : 'light'}
            text="Omnixon"
            color={dark ? '#fafafa' : '#18181b'}
            accentColor={dark ? '#7c8cff' : '#4f46e5'}
            fontWeight={700}
            reach={220}
            labels
            selection
          />
        </div>
        <div className="relative z-10 flex items-center justify-between p-6 text-xs text-muted-foreground">
          <span>{t('Hover the wordmark. Drag a letter.')}</span>
          <Link to="/" className="underline-offset-4 hover:underline">
            {t('About Omnixon')}
          </Link>
        </div>
      </div>

      <div className="relative flex items-center justify-center p-6">
        <div className="absolute top-4 right-4 flex items-center gap-1">
          <LanguageSwitch />
          <Button variant="ghost" size="icon-sm" aria-label={t('Toggle theme')} onClick={() => setTheme(dark ? 'light' : 'dark')}>
            {dark ? <SunIcon /> : <MoonIcon />}
          </Button>
        </div>
        <form onSubmit={submit} className="grid w-full max-w-sm gap-6">
          <div className="grid gap-1.5">
            <h1 className="text-2xl font-semibold tracking-tight">{t('Sign in')}</h1>
            <p className="text-sm text-muted-foreground">{t("Use the Bearer token of any role. The first one, an owner, is the service's INITIAL_API_KEY.")}</p>
          </div>
          <FieldGroup>
            <FormField label={t('Token')}>
              <Input type="password" autoFocus autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} placeholder={t('Your token')} />
            </FormField>
            <FormField label={t('API URL (optional)')} description={t("Leave empty to use this site's own /api proxy. A direct URL needs CORS on the service.")}>
              <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="http://localhost:8083" />
            </FormField>
          </FieldGroup>
          {error && (
            <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" size="lg" disabled={busy || !token.trim()}>
            {busy ? <Spinner /> : <KeyRoundIcon />} {t('Sign in')}
          </Button>
        </form>
      </div>
    </div>
  )
}

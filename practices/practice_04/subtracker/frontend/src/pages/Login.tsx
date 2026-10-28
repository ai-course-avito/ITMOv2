import { useId, useState, type FormEvent } from 'react'
import { ApiError, NetworkError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Check, LogoMark } from '../components/Icons'
import { LangSwitch, ThemeToggle } from '../components/Switches'
import { useT } from '../i18n'

type Mode = 'login' | 'register'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function Login() {
  const t = useT()
  const { login, register } = useAuth()
  const emailId = useId()
  const passwordId = useId()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({})
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)

  const isLogin = mode === 'login'

  function switchMode(next: Mode) {
    setMode(next)
    setErrors({})
    setFormError('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setFormError('')
    const found: typeof errors = {}
    if (!email.trim()) found.email = t.auth.errRequired
    else if (!EMAIL_RE.test(email.trim())) found.email = t.auth.errEmail
    if (!password) found.password = t.auth.errRequired
    else if (!isLogin && password.length < 8) found.password = t.auth.errPassword
    setErrors(found)
    if (found.email || found.password) return

    setBusy(true)
    try {
      if (isLogin) await login(email.trim(), password)
      else await register(email.trim(), password)
    } catch (error) {
      if (error instanceof NetworkError) setFormError(t.common.errorNetwork)
      else if (error instanceof ApiError && error.status === 401) setFormError(t.auth.errCredentials)
      else if (error instanceof ApiError && error.status === 409) setFormError(t.auth.errEmailTaken)
      else if (error instanceof ApiError && error.status === 422) setFormError(t.auth.errEmail)
      else setFormError(t.common.errorGeneric)
    } finally {
      setBusy(false)
    }
  }

  const input = (error?: string) =>
    `h-[52px] w-full rounded-2xl border bg-surface px-[18px] text-[15px] text-text outline-none focus:border-accent ${error ? 'border-red-400' : 'border-line'}`

  return (
    <div className="mx-auto grid min-h-screen max-w-[1360px] gap-6 p-4 md:p-6 lg:grid-cols-[1.1fr_1fr]">
      <section className="card hidden flex-col justify-between rounded-[32px] px-12 py-11 lg:flex">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-[11px] bg-accent text-accent-text">
            <LogoMark size={20} />
          </div>
          <span className="text-xl font-medium">{t.brand}</span>
        </div>
        <div>
          <span className="mb-[18px] inline-block rounded-full border border-line px-3 py-[5px] text-xs text-muted">
            {t.auth.badge}
          </span>
          <h2 className="m-0 max-w-[420px] text-[52px] leading-[1.08] font-light tracking-tight">{t.auth.heroTitle}</h2>
          <p className="mt-5 mb-0 max-w-[420px] text-base leading-relaxed text-muted">{t.auth.heroText}</p>
          <ul className="m-0 mt-8 flex list-none flex-col gap-3.5 p-0">
            {[t.auth.feature1, t.auth.feature2, t.auth.feature3].map((text, i, all) => (
              <li
                key={text}
                className={`flex items-center gap-3 text-[15px] ${i < all.length - 1 ? 'border-b border-line pb-3.5' : ''}`}
              >
                <Check size={20} className="text-accent" />
                {text}
              </li>
            ))}
          </ul>
        </div>
        <p className="m-0 text-[13px] text-muted">{t.auth.privacy}</p>
      </section>

      <section className="flex flex-col px-2 py-2 md:px-6">
        <div className="flex h-12 items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 lg:invisible">
            <div className="flex size-8 items-center justify-center rounded-[10px] bg-accent text-accent-text">
              <LogoMark size={18} />
            </div>
            <span className="text-lg font-medium">{t.brand}</span>
          </div>
          <div className="flex items-center gap-3">
            <LangSwitch />
            <ThemeToggle />
          </div>
        </div>

        <div className="m-auto w-full max-w-[400px] py-8">
          <div role="tablist" className="mb-8 flex rounded-full border border-line bg-surface p-1">
            {(['login', 'register'] as const).map((value) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={mode === value}
                onClick={() => switchMode(value)}
                className={`flex-1 rounded-full py-[11px] text-sm ${mode === value ? 'bg-accent font-medium text-accent-text' : 'text-muted'}`}
              >
                {value === 'login' ? t.auth.loginTab : t.auth.registerTab}
              </button>
            ))}
          </div>

          <h1 className="m-0 mb-2 text-3xl font-light tracking-tight">{isLogin ? t.auth.loginTitle : t.auth.registerTitle}</h1>
          <p className="m-0 mb-7 text-sm text-muted">{isLogin ? t.auth.loginSub : t.auth.registerSub}</p>

          <form onSubmit={submit} noValidate>
            <label htmlFor={emailId} className="mb-2 block text-[13px] text-muted">{t.auth.email}</label>
            <input
              id={emailId}
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={Boolean(errors.email)}
              className={input(errors.email)}
            />
            {errors.email && <p role="alert" className="mt-1.5 mb-0 text-xs text-red-400">{errors.email}</p>}

            <label htmlFor={passwordId} className="mt-[18px] mb-2 block text-[13px] text-muted">
              {t.auth.password}
              {!isLogin && <span className="ml-2 opacity-70">({t.auth.passwordHint})</span>}
            </label>
            <input
              id={passwordId}
              type="password"
              autoComplete={isLogin ? 'current-password' : 'new-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={Boolean(errors.password)}
              className={input(errors.password)}
            />
            {errors.password && <p role="alert" className="mt-1.5 mb-0 text-xs text-red-400">{errors.password}</p>}

            {formError && <p role="alert" className="mt-4 mb-0 text-sm text-red-400">{formError}</p>}

            <button
              type="submit"
              disabled={busy}
              className="mt-7 h-[54px] w-full rounded-full bg-accent text-[15px] font-semibold text-accent-text disabled:opacity-60"
            >
              {busy ? t.auth.submitting : isLogin ? t.auth.signIn : t.auth.signUp}
            </button>
          </form>

          <p className="mt-5 mb-0 text-center text-[13px] text-muted">
            {isLogin ? t.auth.noAccount : t.auth.haveAccount}{' '}
            <button
              type="button"
              onClick={() => switchMode(isLogin ? 'register' : 'login')}
              className="border-0 bg-transparent p-0 font-medium text-accent"
            >
              {isLogin ? t.auth.signUp : t.auth.signIn}
            </button>
          </p>
        </div>
      </section>
    </div>
  )
}

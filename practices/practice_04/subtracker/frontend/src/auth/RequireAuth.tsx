import { Navigate, Outlet } from 'react-router-dom'
import { useT } from '../i18n'
import { useAuth } from './AuthContext'

export function RequireAuth() {
  const { status, retry } = useAuth()
  const t = useT()

  if (status === 'loading') {
    return <p role="status" className="p-10 text-muted">{t.common.loading}</p>
  }
  if (status === 'error') {
    return (
      <div role="alert" className="mx-auto max-w-md p-10 text-center">
        <p className="mb-4 text-muted">{t.common.errorNetwork}</p>
        <button type="button" onClick={retry} className="rounded-full bg-accent px-6 py-3 font-semibold text-accent-text">
          {t.common.retry}
        </button>
      </div>
    )
  }
  if (status === 'anon') return <Navigate to="/login" replace />
  return <Outlet />
}

export function RedirectIfAuthed() {
  const { status } = useAuth()
  if (status === 'authed') return <Navigate to="/" replace />
  return <Outlet />
}

import { useCallback, useMemo, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import type { Subscription } from '../api/types'
import { useT } from '../i18n'
import { AdBanner } from './AdBanner'
import { DataVersionProvider, useDataVersion } from './DataVersion'
import { Lock, LogoMark, Plus, SignOut } from './Icons'
import { LangSwitch, ThemeToggle } from './Switches'
import { SubscriptionPanel } from './SubscriptionPanel'
import { PanelContext, type PanelValue } from './panelContext'

export function AppLayout() {
  return (
    <DataVersionProvider>
      <Shell />
    </DataVersionProvider>
  )
}

const tabClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-full px-[22px] py-2.5 text-sm no-underline ${isActive ? 'bg-accent font-medium text-accent-text' : 'text-muted'}`

const mobileTabClass = ({ isActive }: { isActive: boolean }) =>
  `flex h-[52px] flex-1 items-center justify-center rounded-full text-[13px] no-underline ${isActive ? 'bg-accent font-semibold text-accent-text' : 'text-muted'}`

function CalendarTab({ mobile }: { mobile?: boolean }) {
  const t = useT()
  // Pro feature: shown with a lock, intentionally navigates nowhere.
  return (
    <button
      type="button"
      aria-disabled="true"
      title={t.nav.calendarLocked}
      aria-label={`${t.nav.calendar}. ${t.nav.calendarLocked}`}
      className={
        mobile
          ? 'flex h-[52px] flex-1 cursor-not-allowed items-center justify-center gap-1.5 rounded-full text-[13px] text-muted opacity-75'
          : 'flex cursor-not-allowed items-center gap-2 rounded-full px-[18px] py-2.5 text-sm text-muted opacity-75'
      }
    >
      {t.nav.calendar}
      <Lock size={mobile ? 12 : 14} />
      {!mobile && <span className="rounded-full border border-line px-[7px] py-0.5 text-[11px] font-semibold tracking-wide">PRO</span>}
    </button>
  )
}

function Shell() {
  const { user, logout } = useAuth()
  const t = useT()
  const { bump } = useDataVersion()
  const [panel, setPanel] = useState<{ subscription: Subscription | null } | null>(null)

  const open = useCallback((subscription: Subscription | null = null) => setPanel({ subscription }), [])
  const close = useCallback(() => setPanel(null), [])
  const value = useMemo<PanelValue>(() => ({ open }), [open])

  return (
    <PanelContext.Provider value={value}>
      <div className="mx-auto flex min-h-screen max-w-[1360px] flex-col gap-3 px-5 pb-28 md:gap-7 md:px-10 md:pb-6">
        {/* desktop header */}
        <header className="hidden h-[88px] shrink-0 items-center justify-between md:flex">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-[11px] bg-accent text-accent-text">
              <LogoMark size={20} />
            </div>
            <span className="text-xl font-medium tracking-tight">{t.brand}</span>
          </div>
          <nav aria-label={t.nav.main} className="flex gap-1 rounded-full border border-line bg-surface p-1">
            <NavLink to="/" end className={tabClass}>{t.nav.overview}</NavLink>
            <NavLink to="/subscriptions" className={tabClass}>{t.nav.subscriptions}</NavLink>
            <CalendarTab />
          </nav>
          <div className="flex items-center gap-3">
            <LangSwitch />
            <ThemeToggle />
            <span className="rounded-full border border-line px-3 py-1.5 text-xs font-medium text-muted">
              {user ? t.nav.plan[user.plan] : ''}
            </span>
            <button
              type="button"
              onClick={logout}
              aria-label={t.nav.signOut}
              title={t.nav.signOut}
              className="flex size-10 items-center justify-center rounded-full border border-line bg-surface text-text"
            >
              <SignOut />
            </button>
            <button
              type="button"
              onClick={() => open(null)}
              className="flex h-11 items-center gap-2 rounded-full bg-accent px-5 text-sm font-semibold text-accent-text"
            >
              <Plus size={16} />
              {t.nav.add}
            </button>
          </div>
        </header>

        {/* mobile top bar */}
        <header className="flex h-16 shrink-0 items-center justify-between md:hidden">
          <div className="flex items-center gap-2.5">
            <div className="flex size-8 items-center justify-center rounded-[10px] bg-accent text-accent-text">
              <LogoMark size={18} />
            </div>
            <span className="text-lg font-medium">{t.brand}</span>
          </div>
          <div className="flex items-center gap-2">
            <LangSwitch />
            <ThemeToggle />
            <button
              type="button"
              onClick={logout}
              aria-label={t.nav.signOut}
              className="flex size-11 items-center justify-center rounded-full border border-line bg-surface text-text"
            >
              <SignOut />
            </button>
          </div>
        </header>

        <main className="flex flex-1 flex-col gap-3 md:gap-7">
          <Outlet />
        </main>

        <AdBanner />
      </div>

      {/* mobile: floating add button + bottom navigation */}
      <button
        type="button"
        onClick={() => open(null)}
        aria-label={t.nav.addSubscription}
        className="fixed right-5 bottom-[100px] z-20 flex size-[60px] items-center justify-center rounded-full bg-accent text-accent-text shadow-[0_8px_24px_rgba(0,0,0,0.35)] md:hidden"
      >
        <Plus size={26} />
      </button>
      <nav
        aria-label={t.nav.main}
        className="fixed inset-x-5 bottom-4 z-20 flex h-16 items-center gap-1 rounded-full border border-line bg-surface p-1.5 md:hidden"
      >
        <NavLink to="/" end className={mobileTabClass}>{t.nav.overview}</NavLink>
        <NavLink to="/subscriptions" className={mobileTabClass}>{t.nav.subscriptions}</NavLink>
        <CalendarTab mobile />
      </nav>

      {panel && (
        <SubscriptionPanel
          subscription={panel.subscription}
          onClose={close}
          onSaved={() => {
            close()
            bump()
          }}
        />
      )}
    </PanelContext.Provider>
  )
}

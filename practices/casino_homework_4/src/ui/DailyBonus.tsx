import { useEffect, useState } from 'react'
import { bonusEligibility } from '../core/bonus'
import { useBalance } from '../store/balance'

const BONUS_STORAGE_KEY = 'luckyspin.bonus.v1'

function loadLastClaim(): string | null {
  try { return localStorage.getItem(BONUS_STORAGE_KEY) } catch { return null }
}
function saveLastClaim(iso: string) {
  try { localStorage.setItem(BONUS_STORAGE_KEY, iso) } catch { /* ignore */ }
}

export function DailyBonus() {
  const { add } = useBalance()
  const [lastClaimedAtISO, setLastClaimedAtISO] = useState<string | null>(loadLastClaim())
  const [eligible, setEligible] = useState(false)
  const [nextResetAtISO, setNextResetAtISO] = useState('')

  useEffect(() => {
    const res = bonusEligibility({ lastClaimedAtISO })
    setEligible(res.eligible)
    setNextResetAtISO(res.nextResetAtISO)
  }, [lastClaimedAtISO])

  const claim = () => {
    if (!eligible) return
    const reward = 50
    add(reward, 'bonus')
    const now = new Date().toISOString()
    setLastClaimedAtISO(now)
    saveLastClaim(now)
  }

  return (
    <div className="space-y-3 p-4 bg-slate-900 border border-slate-700 rounded">
      <h2 className="text-xl font-semibold">Daily Bonus</h2>
      <div className="text-sm text-slate-400">Next reset: {new Date(nextResetAtISO).toLocaleString()}</div>
      <button
        onClick={claim}
        disabled={!eligible}
        className="px-3 py-2 rounded bg-primary text-primary-fg disabled:opacity-50"
      >
        {eligible ? 'Claim 50' : 'Come back later'}
      </button>
    </div>
  )
}

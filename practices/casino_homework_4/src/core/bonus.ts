export interface BonusState {
  lastClaimedAtISO: string | null
}

export interface BonusResult {
  eligible: boolean
  nextResetAtISO: string
}

function dateOnlyISO(d: Date): string {
  const y = d.getUTCFullYear()
  const m = String(d.getUTCMonth() + 1).padStart(2, '0')
  const day = String(d.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function midnightNextUTC(from: Date): string {
  const n = new Date(Date.UTC(from.getUTCFullYear(), from.getUTCMonth(), from.getUTCDate() + 1))
  return n.toISOString()
}

export function bonusEligibility(state: BonusState, now: Date = new Date()): BonusResult {
  if (!state.lastClaimedAtISO) {
    return { eligible: true, nextResetAtISO: midnightNextUTC(now) }
  }
  const last = new Date(state.lastClaimedAtISO)
  if (isNaN(last.getTime())) {
    return { eligible: true, nextResetAtISO: midnightNextUTC(now) }
  }
  const eligible = dateOnlyISO(now) !== dateOnlyISO(last)
  const boundary = eligible ? now : last
  return { eligible, nextResetAtISO: midnightNextUTC(boundary) }
}

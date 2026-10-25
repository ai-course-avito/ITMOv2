import { defaultRng } from '../core/random'
import { spin } from '../core/slot'
import { useBalance } from '../store/balance'
import { useState } from 'react'

export function Lobby() {
  const { balance, add } = useBalance()
  const [bet, setBet] = useState(10)
  const [symbols, setSymbols] = useState<string[] | null>(null)
  const [lastWin, setLastWin] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const onSpin = () => {
    setError(null)
    try {
      const res = spin({ balance, bet }, defaultRng)
      setSymbols(res.symbols)
      setLastWin(res.win)
      add(-bet + res.win, 'spin')
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-lg">Balance: <span className="text-accent">{balance}</span></div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-400">Bet</label>
          <input
            className="w-24 bg-slate-900 border border-slate-700 rounded px-2 py-1"
            type="number" value={bet} min={1} onChange={(e) => setBet(Number(e.target.value))}
          />
          <button onClick={onSpin} className="px-3 py-1 bg-primary text-primary-fg rounded">Spin</button>
        </div>
      </div>

      {error && <div className="text-red-400">{error}</div>}

      <div className="grid grid-cols-3 gap-2 text-3xl">
        {(symbols ?? ['?', '?', '?']).map((s, i) => (
          <div key={i} className="bg-slate-900 border border-slate-700 rounded p-4 text-center">{s}</div>
        ))}
      </div>

      <div className="text-sm text-slate-400">Last win: {lastWin}</div>
    </div>
  )
}

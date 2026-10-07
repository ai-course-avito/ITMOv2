import { Lobby } from './Lobby'
import { DailyBonus } from './DailyBonus'

export function App() {
  return (
    <div className="min-h-full bg-slate-950 text-slate-100">
      <header className="p-4 border-b border-slate-800">
        <h1 className="text-2xl font-bold">LuckySpin</h1>
      </header>
      <main className="p-4 grid gap-6 md:grid-cols-3">
        <section className="md:col-span-2"><Lobby /></section>
        <aside><DailyBonus /></aside>
      </main>
    </div>
  )
}

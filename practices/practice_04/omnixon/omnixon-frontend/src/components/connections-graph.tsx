import type { ComponentType } from 'react'
import { BrainCircuitIcon, CalendarCheckIcon, CpuIcon, Gamepad2Icon, GlobeIcon, HeadphonesIcon, LibraryBigIcon, MessageCircleIcon, SendIcon, ServerIcon, ShoppingBagIcon, SparklesIcon, StoreIcon } from 'lucide-react'
import { Logo } from '@/components/logo'
import { cn } from '@/lib/utils'

/*
 * Who talks to whom: the channels where people write (a bot, a site), Omnixon in the middle, the agents behind it and the models they run on.
 * Four columns of cards over one SVG of curves. The SVG is drawn in a 100 x 100 box stretched over the whole figure (so the
 * lines meet the cards at any width) with non-scaling strokes; the cards are placed by the same percentages.
 */

interface Node {
  id: string
  label: string
  note?: string
  icon?: ComponentType<{ className?: string }>
  /** The colour of the brand, for a messenger: it is the only colour in the figure. */
  brand?: string
  /** Letters instead of an icon, for a brand with no fitting icon. */
  glyph?: string
}

// the messengers carry their brand colours (a tile with a white mark); everything else in the figure stays neutral
const CHANNELS: Node[] = [
  { id: 'telegram', label: 'Telegram', icon: SendIcon, brand: '#229ED9' },
  { id: 'whatsapp', label: 'WhatsApp', icon: MessageCircleIcon, brand: '#25D366' },
  { id: 'discord', label: 'Discord', icon: Gamepad2Icon, brand: '#5865F2' },
  { id: 'avito', label: 'Avito', icon: StoreIcon, brand: '#0099F7' },
  { id: 'vk', label: 'VK', glyph: 'VK', brand: '#0077FF' },
  { id: 'site', label: 'Your website', icon: GlobeIcon },
]
const AGENTS: Node[] = [
  { id: 'support', label: 'Support agent', note: 'knows the docs', icon: HeadphonesIcon },
  { id: 'sales', label: 'Sales agent', note: 'remembers clients', icon: ShoppingBagIcon },
  { id: 'docs', label: 'Docs helper', note: 'answers from docs', icon: LibraryBigIcon },
  { id: 'booking', label: 'Booking agent', note: 'books by chat', icon: CalendarCheckIcon },
]
const MODELS: Node[] = [
  { id: 'gpt', label: 'GPT', icon: SparklesIcon },
  { id: 'claude', label: 'Claude', icon: BrainCircuitIcon },
  { id: 'gemini', label: 'Gemini', icon: CpuIcon },
  { id: 'local', label: 'Own server', note: 'vLLM, Ollama', icon: ServerIcon },
]
// one agent, one model, shuffled so the lines cross
const RUNS_ON: [string, string][] = [
  ['support', 'claude'],
  ['sales', 'local'],
  ['docs', 'gpt'],
  ['booking', 'gemini'],
]

// columns: where a column of cards starts and ends (percent of the width)
const COL = { channels: [0, 19], hub: [31, 52], agents: [60, 79], models: [86, 100] } as const

const centreY = (index: number, count: number) => ((index + 0.5) / count) * 100

function edge(x1: number, y1: number, x2: number, y2: number) {
  const mid = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`
}

function Card({ node, left, width, top, className }: { node: Node; left: number; width: number; top: number; className?: string }) {
  const Icon = node.icon
  return (
    <div
      data-node={node.id}
      className={cn('absolute flex min-h-10 -translate-y-1/2 items-center gap-2 rounded-lg border bg-card px-2.5 py-1.5 text-left shadow-sm', className)}
      style={{ left: `${left}%`, width: `${width}%`, top: `${top}%` }}
    >
      {node.brand ? (
        <span data-brand={node.brand} className="flex size-6 shrink-0 items-center justify-center rounded-md text-[0.65rem] font-bold leading-none text-white" style={{ backgroundColor: node.brand }}>
          {Icon ? <Icon className="size-3.5" /> : node.glyph}
        </span>
      ) : (
        Icon && <Icon className="size-4 shrink-0 text-muted-foreground" />
      )}
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium leading-tight">{node.label}</span>
        {node.note && <span className="hidden truncate text-xs leading-tight text-muted-foreground lg:block">{node.note}</span>}
      </span>
    </div>
  )
}

export function ConnectionsGraph({ className }: { className?: string }) {
  const hubY = 50
  const edges: { key: string; d: string }[] = [
    ...CHANNELS.map((c, i) => ({ key: `${c.id}-hub`, d: edge(COL.channels[1], centreY(i, CHANNELS.length), COL.hub[0], hubY) })),
    ...AGENTS.map((a, i) => ({ key: `hub-${a.id}`, d: edge(COL.hub[1], hubY, COL.agents[0], centreY(i, AGENTS.length)) })),
    ...RUNS_ON.map(([agent, model]) => ({
      key: `${agent}-${model}`,
      d: edge(COL.agents[1], centreY(AGENTS.findIndex((a) => a.id === agent), AGENTS.length), COL.models[0], centreY(MODELS.findIndex((m) => m.id === model), MODELS.length)),
    })),
  ]
  return (
    <figure className={cn('w-full', className)}>
      <div className="overflow-x-auto pb-2">
        <div role="img" aria-label="Channels such as Telegram, WhatsApp and a website send their messages to Omnixon, which hands them to agents that run on different language models" className="relative mx-auto h-[28rem] min-w-[40rem] max-w-5xl">
          <svg className="absolute inset-0 size-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
            {edges.map((e) => (
              <path key={e.key} data-edge={e.key} d={e.d} fill="none" className="stroke-border" strokeWidth={2} vectorEffect="non-scaling-stroke" />
            ))}
            {edges.map((e) => (
              <path key={`flow-${e.key}`} d={e.d} fill="none" className="graph-flow stroke-foreground/45" strokeWidth={1.5} strokeDasharray="2 14" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
            ))}
          </svg>

          {CHANNELS.map((c, i) => (
            <Card key={c.id} node={c} left={COL.channels[0]} width={COL.channels[1] - COL.channels[0]} top={centreY(i, CHANNELS.length)} />
          ))}

          <div
            data-node="omnixon"
            className="absolute flex -translate-y-1/2 flex-col items-center gap-2 rounded-xl border bg-card px-3 py-5 text-center shadow-md"
            style={{ left: `${COL.hub[0]}%`, width: `${COL.hub[1] - COL.hub[0]}%`, top: `${hubY}%` }}
          >
            <Logo className="size-9" />
            <span className="font-semibold leading-none">Omnixon</span>
            <span className="text-xs leading-snug text-muted-foreground">history, memory, knowledge base, tools</span>
          </div>

          {AGENTS.map((a, i) => (
            <Card key={a.id} node={a} left={COL.agents[0]} width={COL.agents[1] - COL.agents[0]} top={centreY(i, AGENTS.length)} />
          ))}
          {MODELS.map((m, i) => (
            <Card key={m.id} node={m} left={COL.models[0]} width={COL.models[1] - COL.models[0]} top={centreY(i, MODELS.length)} />
          ))}

          {[
            ['Channels', COL.channels],
            ['Agents', COL.agents],
            ['Models', COL.models],
          ].map(([label, col]) => (
            <span key={label as string} className="absolute -top-1 -translate-y-full text-xs font-medium uppercase tracking-wide text-muted-foreground" style={{ left: `${(col as readonly number[])[0]}%` }}>
              {label as string}
            </span>
          ))}
        </div>
      </div>
      <figcaption className="sr-only">Every channel talks to the same Omnixon; every agent can run on any model, including your own server.</figcaption>
    </figure>
  )
}

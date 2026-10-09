import type { ReactNode } from 'react'
import { BrainCircuitIcon, ChevronRightIcon, CoinsIcon, LoaderCircleIcon, TimerIcon, TriangleAlertIcon, WrenchIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { ChainOfThought, ChainOfThoughtContent, ChainOfThoughtHeader, ChainOfThoughtSearchResult, ChainOfThoughtSearchResults, ChainOfThoughtStep } from '@/components/ai-elements/chain-of-thought'
import { fmtMs, pretty } from '@/lib/format'
import { plural, t } from '@/lib/i18n'
import type { TraceStep } from '@/lib/types'

/** Arguments or a result of a tool: a line when it is short, a folded JSON when it is not. */
function Data({ label, value }: { label: string; value: unknown }) {
  const text = typeof value === 'string' ? value : pretty(value)
  if (text.length <= 80 && !text.includes('\n')) {
    return (
      <div className="flex gap-2 text-xs">
        <span className="text-muted-foreground">{label}</span>
        <code className="min-w-0 font-mono break-all">{text}</code>
      </div>
    )
  }
  return (
    <Collapsible>
      <CollapsibleTrigger className="group/data flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
        <ChevronRightIcon className="size-3 transition-transform group-data-panel-open/data:rotate-90" /> {label}
      </CollapsibleTrigger>
      <CollapsibleContent>
        <pre className="mt-1 max-h-56 overflow-auto rounded-md border bg-muted/40 p-2 font-mono text-xs whitespace-pre-wrap">{text}</pre>
      </CollapsibleContent>
    </Collapsible>
  )
}

function Step({ s }: { s: TraceStep }) {
  const isTool = s.kind === 'tool'
  const failed = !!s.error
  const facts: ReactNode[] = []
  if (s.duration_ms !== undefined)
    facts.push(
      <span key="time" className="inline-flex items-center gap-1">
        <TimerIcon className="size-3" /> {fmtMs(s.duration_ms)}
      </span>,
    )
  if (s.input_tokens || s.output_tokens)
    facts.push(
      <span key="tokens" className="inline-flex items-center gap-1">
        <CoinsIcon className="size-3" /> {t('{input} in, {output} out', { input: s.input_tokens ?? 0, output: s.output_tokens ?? 0 })}
      </span>,
    )
  return (
    <ChainOfThoughtStep
      icon={failed ? TriangleAlertIcon : isTool ? WrenchIcon : BrainCircuitIcon}
      status={failed ? 'error' : 'complete'}
      label={
        <span className="flex flex-wrap items-center gap-2 text-foreground">
          <span className="font-medium">{isTool ? t('Tool') : t('Model')}</span>
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{s.name}</code>
        </span>
      }
      description={facts.length ? <span className="flex flex-wrap items-center gap-x-3 gap-y-1">{facts}</span> : undefined}
    >
      {/* what the model wrote is not repeated here: it is the answer, right below the chain */}
      {s.args !== undefined && s.args !== null && <Data label={t('arguments')} value={s.args} />}
      {s.result !== undefined && s.result !== null && <Data label={t('result')} value={s.result} />}
      {s.error && <p className="text-xs">{s.error}</p>}
    </ChainOfThoughtStep>
  )
}

/** The chain of calls behind an answer: each call to the model and each tool it called. */
export function TraceView({ steps, running }: { steps: TraceStep[]; running?: boolean }) {
  const tools = steps.filter((s) => s.kind === 'tool').length
  const ms = steps.reduce((sum, s) => sum + (s.duration_ms ?? 0), 0)
  const tokens = steps.reduce((sum, s) => sum + (s.input_tokens ?? 0) + (s.output_tokens ?? 0), 0)
  return (
    <ChainOfThought defaultOpen className="w-full max-w-[85%] rounded-xl border bg-background p-3">
      <ChainOfThoughtHeader>
        <span className="flex items-center gap-2">
          {t('Chain of calls')}
          <Badge variant="secondary">{plural(steps.length, 'step', 'steps')}</Badge>
        </span>
      </ChainOfThoughtHeader>
      <ChainOfThoughtContent>
        <ChainOfThoughtSearchResults>
          <ChainOfThoughtSearchResult>{plural(steps.length - tools, 'model call', 'model calls')}</ChainOfThoughtSearchResult>
          <ChainOfThoughtSearchResult>{plural(tools, 'tool call', 'tool calls')}</ChainOfThoughtSearchResult>
          {ms > 0 && <ChainOfThoughtSearchResult>{fmtMs(ms)}</ChainOfThoughtSearchResult>}
          {tokens > 0 && <ChainOfThoughtSearchResult>{plural(tokens, 'token', 'tokens')}</ChainOfThoughtSearchResult>}
        </ChainOfThoughtSearchResults>
        {steps.map((s) => (
          <Step key={s.step} s={s} />
        ))}
        {running && (
          <ChainOfThoughtStep icon={LoaderCircleIcon} status="active" label={t('Working…')} />
        )}
      </ChainOfThoughtContent>
    </ChainOfThought>
  )
}


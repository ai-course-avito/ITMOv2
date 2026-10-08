import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, XAxis, YAxis } from 'recharts'
import { CalendarDaysIcon, CalendarRangeIcon, ChartColumnIcon, CoinsIcon, TimerIcon, TriangleAlertIcon, ZapIcon } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart'
import { Skeleton } from '@/components/ui/skeleton'
import CountUp from '@/components/CountUp'
import { AgentField } from '@/components/agent-field'
import { DataTable } from '@/components/data-table'
import { FormField, OptionCombobox, OptionSelect, type Option } from '@/components/form'
import { ErrorBox, Page, PageHeader, PageScroll, QueryBar } from '@/components/page'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useAgents, useTokens } from '@/lib/data'
import { fmtMs } from '@/lib/format'
import { tokenOption } from '@/lib/options'
import type { DailyUsage, MonthlyUsage, UsageRow } from '@/lib/types'

const money = (v: number) => (v >= 1 ? `$${v.toFixed(2)}` : v === 0 ? '$0' : `$${v.toPrecision(2)}`)
const compact = (v: number) => new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(v)
const PALETTE = ['var(--chart-3)', 'var(--chart-2)', 'var(--chart-4)', 'var(--chart-1)', 'var(--chart-5)']

const sum = (rows: UsageRow[], key: 'requests' | 'errors' | 'input_tokens' | 'output_tokens' | 'cost' | 'duration_ms_sum') => rows.reduce((n, r) => n + r[key], 0)

/** The days of the period, each with what was spent (zeros for quiet days, so a chart has no holes). */
function byDay(rows: DailyUsage[], days: number) {
  const out = new Map<string, { day: string; ok: number; errors: number; input: number; output: number; cost: number }>()
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    const day = d.toLocaleDateString('en-CA') // YYYY-MM-DD in the local time
    out.set(day, { day, ok: 0, errors: 0, input: 0, output: 0, cost: 0 })
  }
  for (const r of rows) {
    const e = out.get(r.day)
    if (!e) continue
    e.ok += r.requests - r.errors
    e.errors += r.errors
    e.input += r.input_tokens
    e.output += r.output_tokens
    e.cost += r.cost
  }
  return [...out.values()]
}

function group<T extends UsageRow>(rows: T[], by: (r: T) => string) {
  const out = new Map<string, { key: string; requests: number; errors: number; input: number; output: number; cost: number; ms: number }>()
  for (const r of rows) {
    const key = by(r)
    const e = out.get(key) ?? { key, requests: 0, errors: 0, input: 0, output: 0, cost: 0, ms: 0 }
    e.requests += r.requests
    e.errors += r.errors
    e.input += r.input_tokens
    e.output += r.output_tokens
    e.cost += r.cost
    e.ms += r.duration_ms_sum
    out.set(key, e)
  }
  return [...out.values()].sort((a, b) => b.cost - a.cost || b.requests - a.requests)
}

type Summary = ReturnType<typeof group>[number]

/** What stands in the place of a chart that has nothing to draw: it says why and what to do, instead of an empty frame. */
function ChartEmpty({ icon: Icon = ChartColumnIcon, title, children, className = 'h-56', ...rest }: { icon?: typeof ZapIcon; title: string; children?: React.ReactNode; className?: string; 'data-testid'?: string }) {
  return (
    <div {...rest} className={`grid place-items-center rounded-lg border border-dashed px-6 text-center ${className}`}>
      <div className="grid justify-items-center gap-1.5">
        <span className="grid size-9 place-items-center rounded-lg border bg-muted text-muted-foreground">
          <Icon className="size-4" />
        </span>
        <p className="text-sm font-medium">{title}</p>
        {children && <p className="max-w-sm text-xs text-muted-foreground">{children}</p>}
      </div>
    </div>
  )
}

function Kpi({ icon: Icon, label, value, format, hint }: { icon: typeof ZapIcon; label: string; value: number; format?: (n: number) => string; hint?: string }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription className="flex items-center gap-2">
          <Icon className="size-4" /> {label}
        </CardDescription>
        <CardTitle className="text-2xl tabular-nums" data-testid={`kpi-${label.toLowerCase().replace(/\W+/g, '-')}`}>
          {format ? format(value) : <CountUp to={value} duration={1} />}
        </CardTitle>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </CardHeader>
    </Card>
  )
}

const requestsConfig = { ok: { label: 'Answered', color: 'var(--chart-3)' }, errors: { label: 'Failed', color: 'var(--destructive)' } } satisfies ChartConfig
const tokensConfig = { input: { label: 'Input tokens', color: 'var(--chart-2)' }, output: { label: 'Output tokens', color: 'var(--chart-4)' } } satisfies ChartConfig
const costConfig = { cost: { label: 'Cost', color: 'var(--chart-3)' } } satisfies ChartConfig

const dayTick = (d: string) => d.slice(5)

const summaryColumns = (what: string): ColumnDef<Summary>[] => [
  { accessorKey: 'key', meta: { label: what }, header: what, cell: ({ getValue }) => <span className="font-medium whitespace-nowrap">{getValue<string>()}</span> },
  { accessorKey: 'requests', meta: { label: 'Requests' }, header: () => <span className="whitespace-nowrap">Requests</span>, cell: ({ getValue }) => <span className="whitespace-nowrap tabular-nums">{getValue<number>()}</span> },
  { accessorKey: 'errors', meta: { label: 'Failed' }, header: () => <span className="whitespace-nowrap">Failed</span>, cell: ({ getValue }) => <span className="whitespace-nowrap tabular-nums">{getValue<number>()}</span> },
  { accessorKey: 'input', meta: { label: 'Input' }, header: () => <span className="whitespace-nowrap">Input tokens</span>, cell: ({ getValue }) => <span className="whitespace-nowrap tabular-nums">{compact(getValue<number>())}</span> },
  { accessorKey: 'output', meta: { label: 'Output' }, header: () => <span className="whitespace-nowrap">Output tokens</span>, cell: ({ getValue }) => <span className="whitespace-nowrap tabular-nums">{compact(getValue<number>())}</span> },
  { accessorKey: 'cost', meta: { label: 'Cost' }, header: () => <span className="whitespace-nowrap">Cost</span>, cell: ({ getValue }) => <span className="whitespace-nowrap tabular-nums">{money(getValue<number>())}</span> },
  {
    id: 'avg',
    meta: { label: 'Average time' },
    accessorFn: (r) => (r.requests ? Math.round(r.ms / r.requests) : 0),
    header: () => <span className="whitespace-nowrap">Average time</span>,
    cell: ({ getValue }) => <span className="whitespace-nowrap tabular-nums">{getValue<number>() ? fmtMs(getValue<number>()) : '—'}</span>,
  },
]

export default function Usage() {
  const { token: me, isAdmin } = useAuth()
  const [days, setDays] = useState('30')
  const [tokenId, setTokenId] = useState<string>('all')
  const [agentId, setAgentId] = useState<number | undefined>(undefined) // admin: all agents until one is picked
  const agents = useAgents()
  const tokens = useTokens(agentId ?? me?.agent_id, agentId === undefined)
  const n = Number(days)

  const filters = { token: tokenId === 'all' ? undefined : Number(tokenId), agent: agentId }
  const recent = useQuery({ queryKey: ['usage', n, filters.token, filters.agent], queryFn: () => api.usage(n, filters.token, filters.agent) })
  const monthly = useQuery({ queryKey: ['usage-monthly', filters.token, filters.agent], queryFn: () => api.usageMonthly(filters.token, filters.agent) })

  const rows = recent.data
  const daily = useMemo(() => (rows ? byDay(rows, n) : []), [rows, n])
  const byToken = useMemo(() => (rows ? group(rows, (r) => r.token_name) : []), [rows])
  const byModel = useMemo(() => (rows ? group(rows, (r) => r.model) : []), [rows])
  const months = useMemo(() => {
    const out = new Map<string, { month: string; cost: number; requests: number }>()
    for (const r of monthly.data ?? ([] as MonthlyUsage[])) {
      const e = out.get(r.month) ?? { month: r.month, cost: 0, requests: 0 }
      e.cost += r.cost
      e.requests += r.requests
      out.set(r.month, e)
    }
    // the months in between that had no usage are there too, so a quiet month shows as quiet instead of vanishing
    const found = [...out.values()].sort((a, b) => a.month.localeCompare(b.month))
    if (found.length < 2) return found
    const filled: typeof found = []
    const [first, last] = [found[0].month, found[found.length - 1].month]
    for (let y = Number(first.slice(0, 4)), m = Number(first.slice(5, 7)); ; ) {
      const key = `${y}-${String(m).padStart(2, '0')}-01`
      filled.push(out.get(key) ?? { month: key, cost: 0, requests: 0 })
      if (key >= last) break
      if (++m > 12) (m = 1), y++
    }
    return filled
  }, [monthly.data])

  const tokenOptions: Option[] = [{ value: 'all', label: 'All tokens' }, ...(tokens.data ?? []).map((t) => tokenOption(t, me?.id, agents.data))]
  const total = rows ?? []
  const quiet = !recent.isLoading && sum(total, 'requests') === 0 // nothing to draw in this period
  const modelPie = byModel.slice(0, 5).map((m, i) => ({ model: m.key, cost: m.cost || m.requests * 1e-9, requests: m.requests, fill: PALETTE[i % PALETTE.length] }))
  const modelConfig = Object.fromEntries(modelPie.map((m) => [m.model, { label: m.model, color: m.fill }])) satisfies ChartConfig

  return (
    <Page>
      <PageHeader
        title="Usage"
        description="What the tokens spent on the models: requests, tokens and money, never the texts. A request counts on the token that made it, also when an admin acts as another agent."
      />
      <QueryBar onSubmit={() => undefined}>
        <FormField label="Period" className="w-56">
          <OptionSelect
            value={days}
            onChange={setDays}
            options={[
              { value: '7', label: 'Last 7 days', icon: CalendarDaysIcon },
              { value: '14', label: 'Last 14 days', icon: CalendarDaysIcon },
              { value: '30', label: 'Last 30 days', icon: CalendarRangeIcon, description: 'As far back as usage is kept in detail' },
            ]}
          />
        </FormField>
        <FormField label="Token" className="w-72">
          <OptionCombobox value={tokenId} onChange={setTokenId} options={tokenOptions} placeholder="All tokens" />
        </FormField>
        {isAdmin && (
          <div className="flex items-end gap-2">
            <AgentField label="Agent" className="w-72" agentId={agentId ?? me?.agent_id} onChange={(v) => { setAgentId(Number(v)); setTokenId('all') }} />
            {agentId !== undefined && (
              <button type="button" className="mb-2 text-xs text-muted-foreground underline underline-offset-4" onClick={() => { setAgentId(undefined); setTokenId('all') }}>
                all agents
              </button>
            )}
          </div>
        )}
      </QueryBar>

      {recent.isError ? (
        <ErrorBox error={recent.error} onRetry={() => recent.refetch()} />
      ) : (
        <PageScroll className="grid auto-rows-max content-start gap-4">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            {recent.isLoading ? (
              Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-24" />)
            ) : (
              <>
                <Kpi icon={ZapIcon} label="Requests" value={sum(total, 'requests')} />
                <Kpi icon={TriangleAlertIcon} label="Failed" value={sum(total, 'errors')} />
                <Kpi icon={ChartColumnIcon} label="Tokens" value={sum(total, 'input_tokens') + sum(total, 'output_tokens')} format={compact} hint={`${compact(sum(total, 'input_tokens'))} in, ${compact(sum(total, 'output_tokens'))} out`} />
                <Kpi icon={CoinsIcon} label="Cost" value={sum(total, 'cost')} format={money} />
                <Kpi icon={TimerIcon} label="Average time" value={sum(total, 'requests') ? Math.round(sum(total, 'duration_ms_sum') / sum(total, 'requests')) : 0} format={(v) => (v ? fmtMs(v) : '—')} />
              </>
            )}
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Requests per day</CardTitle>
                <CardDescription>Answered and failed.</CardDescription>
              </CardHeader>
              <CardContent>
                {quiet ? <ChartEmpty title="No requests in this period" icon={ChartColumnIcon}>Requests made with the chosen token show up here as they happen. Try a longer period or another token.</ChartEmpty> : (
<ChartContainer config={requestsConfig} className="h-56 w-full" data-testid="chart-requests">
                  <BarChart data={daily} accessibilityLayer>
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="day" tickLine={false} axisLine={false} tickMargin={8} tickFormatter={dayTick} minTickGap={16} />
                    <YAxis tickLine={false} axisLine={false} width={32} allowDecimals={false} />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <ChartLegend content={<ChartLegendContent />} />
                    <Bar dataKey="ok" stackId="a" fill="var(--color-ok)" radius={[0, 0, 4, 4]} />
                    <Bar dataKey="errors" stackId="a" fill="var(--color-errors)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ChartContainer>
)}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Tokens per day</CardTitle>
                <CardDescription>What went to the models and what came back.</CardDescription>
              </CardHeader>
              <CardContent>
                {quiet ? <ChartEmpty title="No requests in this period" icon={ChartColumnIcon}>Requests made with the chosen token show up here as they happen. Try a longer period or another token.</ChartEmpty> : (
<ChartContainer config={tokensConfig} className="h-56 w-full" data-testid="chart-tokens">
                  <AreaChart data={daily} accessibilityLayer>
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="day" tickLine={false} axisLine={false} tickMargin={8} tickFormatter={dayTick} minTickGap={16} />
                    <YAxis tickLine={false} axisLine={false} width={40} tickFormatter={compact} />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <ChartLegend content={<ChartLegendContent />} />
                    <Area dataKey="input" type="monotone" stackId="t" stroke="var(--color-input)" fill="var(--color-input)" fillOpacity={0.35} />
                    <Area dataKey="output" type="monotone" stackId="t" stroke="var(--color-output)" fill="var(--color-output)" fillOpacity={0.35} />
                  </AreaChart>
                </ChartContainer>
)}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Cost per day</CardTitle>
                <CardDescription>What the provider reported. Calls it did not price add nothing.</CardDescription>
              </CardHeader>
              <CardContent>
                {quiet ? <ChartEmpty title="No requests in this period" icon={ChartColumnIcon}>Requests made with the chosen token show up here as they happen. Try a longer period or another token.</ChartEmpty> : (
<ChartContainer config={costConfig} className="h-56 w-full" data-testid="chart-cost">
                  <LineChart data={daily} accessibilityLayer>
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="day" tickLine={false} axisLine={false} tickMargin={8} tickFormatter={dayTick} minTickGap={16} />
                    <YAxis tickLine={false} axisLine={false} width={48} tickFormatter={money} />
                    <ChartTooltip content={<ChartTooltipContent formatter={(v) => money(Number(v))} />} />
                    <Line dataKey="cost" type="monotone" stroke="var(--color-cost)" strokeWidth={2} dot={false} />
                  </LineChart>
                </ChartContainer>
)}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>By model</CardTitle>
                <CardDescription>Share of the cost (of the requests, when nothing was priced).</CardDescription>
              </CardHeader>
              <CardContent>
                {modelPie.length ? (
                  <ChartContainer config={modelConfig} className="mx-auto h-56 w-full" data-testid="chart-models">
                    <PieChart>
                      <ChartTooltip content={<ChartTooltipContent nameKey="model" hideLabel />} />
                      <Pie data={modelPie} dataKey="cost" nameKey="model" innerRadius={50} strokeWidth={2}>
                        {modelPie.map((m) => (
                          <Cell key={m.model} fill={m.fill} />
                        ))}
                      </Pie>
                      <ChartLegend content={<ChartLegendContent nameKey="model" />} />
                    </PieChart>
                  </ChartContainer>
                ) : (
                  <p className="grid h-56 place-items-center text-sm text-muted-foreground">No requests in this period.</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* two tables side by side only when each has room for a whole row on one line; otherwise one under the other */}
          <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,46rem),1fr))] gap-4">
            <section className="grid min-w-0 gap-2" aria-label="Usage by token">
              <h2 className="text-sm font-medium text-muted-foreground">By token</h2>
              <DataTable columns={summaryColumns('Token')} data={byToken} loading={recent.isLoading} empty={{ icon: ChartColumnIcon, title: 'No usage yet', description: 'Requests show up here as tokens make them.' }} searchPlaceholder="Search tokens…" getRowId={(r) => r.key} />
            </section>
            <section className="grid min-w-0 gap-2" aria-label="Usage by model">
              <h2 className="text-sm font-medium text-muted-foreground">By model</h2>
              <DataTable columns={summaryColumns('Model')} data={byModel} loading={recent.isLoading} empty={{ icon: ChartColumnIcon, title: 'No usage yet' }} searchPlaceholder="Search models…" getRowId={(r) => r.key} />
            </section>
          </div>

          {/* not overflow-hidden: in this scrolling grid such a card is squeezed to its header when the page is taller than the window */}
          <Card className="overflow-visible">
            <CardHeader>
              <CardTitle>Earlier months</CardTitle>
              <CardDescription>Detail is kept for 30 days; older usage is folded into one line per token, month and model, and stays.</CardDescription>
            </CardHeader>
            <CardContent>
              {months.length ? (
                <div className="grid gap-4">
                  <ChartContainer config={costConfig} className="h-48 w-full" data-testid="chart-months">
                    <BarChart data={months} accessibilityLayer>
                      <CartesianGrid vertical={false} />
                      <XAxis dataKey="month" tickLine={false} axisLine={false} tickMargin={8} tickFormatter={(m: string) => m.slice(0, 7)} />
                      <YAxis tickLine={false} axisLine={false} width={48} tickFormatter={money} />
                      <ChartTooltip content={<ChartTooltipContent formatter={(v) => money(Number(v))} />} />
                      <Bar dataKey="cost" fill="var(--color-cost)" radius={4} />
                    </BarChart>
                  </ChartContainer>
                  <ul className="grid gap-1 text-sm sm:grid-cols-2 xl:grid-cols-3" aria-label="Months">
                    {[...months].reverse().map((m) => (
                      <li key={m.month} className="flex items-center justify-between rounded-lg border px-3 py-1.5">
                        <span className="value-mono">{m.month.slice(0, 7)}</span>
                        {m.requests ? (
                          <span className="tabular-nums">
                            {m.requests} requests, {money(m.cost)}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">No usage</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <ChartEmpty icon={CalendarRangeIcon} title="No earlier months yet" className="h-40" data-testid="months-empty">
                  Detail is kept for 30 days. When usage gets older than that it is folded into one line per month and shows up here, and stays.
                </ChartEmpty>
              )}
            </CardContent>
          </Card>
        </PageScroll>
      )}
    </Page>
  )
}

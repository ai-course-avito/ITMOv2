import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { BotIcon, CpuIcon, KeyRoundIcon, PlugIcon } from 'lucide-react'
import CountUp from '@/components/CountUp'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Item, ItemContent, ItemDescription, ItemGroup, ItemMedia, ItemTitle } from '@/components/ui/item'
import { Skeleton } from '@/components/ui/skeleton'
import { groupsFor } from '@/components/nav-items'
import { Page, PageHeader, PageScroll } from '@/components/page'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { modelName, useAgents, useMcpServers, useModels, useSelfAgent, useTokens } from '@/lib/data'
import { fmtDate, truncate } from '@/lib/format'

function Status({ ok, label, detail }: { ok?: boolean; label: string; detail?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`size-2.5 rounded-full ${ok === undefined ? 'bg-muted-foreground/40' : ok ? 'bg-success' : 'bg-destructive'}`} />
      <span className="font-medium">{label}</span>
      {detail && <span className="text-sm text-muted-foreground">{detail}</span>}
    </div>
  )
}

export default function Dashboard() {
  const { token, role, isAdmin } = useAuth()
  const poll = { refetchInterval: 10_000, retry: false }
  const live = useQuery({ queryKey: ['healthz'], queryFn: api.healthz, ...poll })
  const ready = useQuery({ queryKey: ['readyz'], queryFn: api.readyz, ...poll })
  const root = useQuery({ queryKey: ['root'], queryFn: api.root, ...poll })
  const selfAgent = useSelfAgent()
  const agents = useAgents()
  const models = useModels()
  const mcp = useMcpServers()
  const tokens = useTokens(undefined, true)

  const counts = [
    { label: 'Agents', q: agents, to: '/agents', icon: BotIcon },
    { label: 'Models', q: models, to: '/models', icon: CpuIcon },
    { label: 'MCP servers', q: mcp, to: '/mcp-servers', icon: PlugIcon },
    { label: 'Tokens', q: tokens, to: '/tokens', icon: KeyRoundIcon },
  ]
  const selfModel = models.data?.find((m) => m.id === selfAgent.data?.model_id)

  return (
    <Page>
      <PageHeader title="Dashboard" description="Service health, a summary of what is configured, and a way to every part of the panel." />
      <PageScroll className="grid content-start gap-4">
        {isAdmin && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {counts.map((c) => (
            <Link key={c.label} to={c.to}>
              <Card className="transition-colors hover:bg-muted/40">
                <CardHeader>
                  <CardDescription className="flex items-center gap-2">
                    <c.icon className="size-4" /> {c.label}
                  </CardDescription>
                  <CardTitle className="text-3xl tabular-nums">
                    {c.q.isLoading ? <Skeleton className="h-9 w-12" /> : c.q.data ? <CountUp to={c.q.data.length} duration={1.2} /> : '—'}
                  </CardTitle>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Service</CardTitle>
              <CardDescription>Refreshes every 10 seconds.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <Status ok={live.data ? live.data.status === 'ok' : live.isError ? false : undefined} label="Liveness" detail="/healthz" />
              <Status
                ok={ready.data ? ready.data.status === 'ok' : undefined}
                label="Readiness"
                detail={
                  ready.data
                    ? ready.data.status === 'ok'
                      ? `database migrated to ${ready.data.migration}`
                      : `${ready.data.status}${ready.data.expected ? ` (migration ${ready.data.migration} of ${ready.data.expected})` : ''}`
                    : '/readyz'
                }
              />
              <Status ok={root.data ? root.data.status === 'ok' : root.isError ? false : undefined} label="API root" detail="/api/v1/" />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>This session</CardTitle>
              <CardDescription>The token you signed in with.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                Token <span className="font-medium">{token?.name}</span> <Badge variant="secondary">{token?.id}</Badge>{' '}
                <Badge>{token?.is_initial ? `${token.role}, initial` : token?.role}</Badge>
                <span className="text-muted-foreground">created {fmtDate(token?.timestamp)}</span>
              </div>
              {selfAgent.data ? (
                <div className="grid gap-1">
                  <div>
                    Agent{' '}
                    {role !== 'regular' ? (
                      <Link className="font-medium underline-offset-4 hover:underline" to={`/agents/${selfAgent.data.id}`}>
                        {selfAgent.data.name}
                      </Link>
                    ) : (
                      <span className="font-medium">{selfAgent.data.name}</span>
                    )}{' '}
                    {selfModel && <span className="text-muted-foreground">on {modelName(selfModel.request_json)}</span>}
                  </div>
                  <p className="text-muted-foreground">{truncate(selfAgent.data.prompt, 200) || 'No prompt'}</p>
                </div>
              ) : (
                <span className="text-muted-foreground">This token has no agent.</span>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4">
          {groupsFor(role)
            .map((g) => ({ ...g, items: g.items.filter((i) => i.url !== '/') }))
            .map((g) => (
              <section key={g.label} className="grid gap-2">
                <h2 className="text-sm font-medium text-muted-foreground">{g.label}</h2>
                <ItemGroup className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {g.items.map((item) => (
                    <Item key={item.url} variant="outline" render={<Link to={item.url} />} className="transition-colors hover:bg-muted/40">
                      <ItemMedia variant="icon">{item.icon}</ItemMedia>
                      <ItemContent>
                        <ItemTitle>{item.title}</ItemTitle>
                        <ItemDescription>{item.description}</ItemDescription>
                      </ItemContent>
                    </Item>
                  ))}
                </ItemGroup>
              </section>
            ))}
        </div>
      </PageScroll>
    </Page>
  )
}

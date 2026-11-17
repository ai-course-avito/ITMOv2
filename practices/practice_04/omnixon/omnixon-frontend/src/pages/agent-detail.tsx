import { useEffect, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { ArrowLeftIcon, BookOpenIcon, PlusIcon, BrainIcon, EyeIcon, GitCompareIcon, HistoryIcon, PencilIcon, PlugIcon, RotateCcwIcon, UnplugIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Spinner } from '@/components/ui/spinner'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AgentBasics, AgentComment, AgentSettings, configFrom, draftFrom, validateDraft, type AgentDraft } from '@/components/agent-form'
import { AgentDialog } from '@/components/agent-dialog'
import { actionsColumn, createdColumn, DataTable, nameColumn, rowAction, SortHeader } from '@/components/data-table'
import { FormDialog } from '@/components/dialogs'
import { FormField, OptionCombobox } from '@/components/form'
import { ErrorBox, LoadingRows, Page, PageHeader } from '@/components/page'
import { VersionViewer } from '@/components/version-viewer'
import { McpDialog, type McpEditing } from '@/pages/mcp-servers'
import { useAuth } from '@/lib/auth'
import { api, ApiError } from '@/lib/api'
import { useMcpServers, useTokens } from '@/lib/data'
import { mcpOption } from '@/lib/options'
import { fmtDate } from '@/lib/format'
import { t } from '@/lib/i18n'
import { useAction } from '@/lib/queries'
import type { Agent, AgentVersion, MCPServer } from '@/lib/types'

function SettingsTab({ agent }: { agent: Agent }) {
  const versions = useQuery({ queryKey: ['versions', agent.id], queryFn: () => api.versions(agent.id), staleTime: 0 })
  const [draft, setDraft] = useState<AgentDraft>(() => draftFrom(agent))
  useEffect(() => setDraft(draftFrom(agent)), [agent])
  const latest = versions.data?.[0]?.number

  const save = useAction(
    () =>
      api.updateAgent(agent.id, {
        ...(draft.name.trim() !== agent.name ? { name: draft.name.trim() } : {}),
        prompt: draft.prompt,
        model_id: Number(draft.modelId),
        config: configFrom(draft, 'update', agent.config),
        comment: draft.comment || null,
        expected_version: latest, // optimistic lock: refuse if someone changed the agent meanwhile
      }),
    { invalidate: ['agent', 'agents', 'versions', 'self-agent'], success: t('Agent saved') },
  )
  const problem = validateDraft(draft)
  const conflict = save.error instanceof ApiError && save.error.status === 409

  return (
    <div className="grid gap-4">
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t('Name, prompt and model')}</CardTitle>
            <CardDescription>{t('What the agent is.')}</CardDescription>
          </CardHeader>
          <CardContent>
            <AgentBasics draft={draft} onChange={setDraft} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t('Configuration')}</CardTitle>
            <CardDescription>{t('How the agent works. Empty limits use the service defaults.')}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6">
            <AgentSettings draft={draft} onChange={setDraft} />
            <AgentComment draft={draft} onChange={setDraft} />
          </CardContent>
        </Card>
      </div>
      {problem && <p className="text-sm text-destructive">{problem}</p>}
      {conflict && <p className="text-sm text-destructive">{t('The agent changed since you opened it. Reload the page to see the latest version, then apply your edit again.')}</p>}
      <div className="flex items-center gap-2">
        <Button disabled={!!problem || save.isPending || versions.isLoading} onClick={() => save.mutate(undefined)}>
          {save.isPending && <Spinner />} {t('Save changes')}
        </Button>
        <Button variant="outline" onClick={() => setDraft(draftFrom(agent))}>
          {t('Reset')}
        </Button>
        {latest !== undefined && <span className="text-xs text-muted-foreground">{t('Based on version {number}', { number: latest })}</span>}
      </div>
    </div>
  )
}

function McpTab({ agent }: { agent: Agent }) {
  const attached = useQuery({ queryKey: ['agent-mcp', agent.id], queryFn: () => api.agentMcpServers(agent.id) })
  const all = useMcpServers()
  const { isAdmin } = useAuth()
  const [pick, setPick] = useState<string | null>(null)
  const [editing, setEditing] = useState<McpEditing>(null)
  const refresh = ['agent-mcp', 'versions']
  const attach = useAction((mcp: number) => api.attachMcpServer(agent.id, mcp), { invalidate: refresh, success: t('Attached'), onSuccess: () => setPick(null) })
  const detach = useAction((mcp: number) => api.detachMcpServer(agent.id, mcp), { invalidate: refresh, success: t('Detached') })
  const free = (all.data ?? []).filter((s) => !attached.data?.some((a) => a.id === s.id))

  const columns: ColumnDef<MCPServer>[] = [
    { accessorKey: 'id', meta: { label: 'ID' }, header: ({ column }) => <SortHeader column={column} title="ID" />, size: 72, cell: ({ getValue }) => <span className="value-mono">{getValue<number>()}</span> },
    nameColumn<MCPServer>((s) => `/mcp-servers?open=${s.id}`),
    {
      id: 'url',
      meta: { label: 'URL' },
      accessorFn: (s) => String(s.config.url ?? ''),
      header: ({ column }) => <SortHeader column={column} title="URL" />,
      cell: ({ getValue }) => <span className="value-mono">{getValue<string>()}</span>,
    },
    {
      id: 'transport',
      meta: { label: t('Transport') },
      accessorFn: (s) => String(s.config.transport ?? 'streamable_http'),
      header: t('Transport'),
      cell: ({ getValue }) => <Badge variant="secondary">{getValue<string>()}</Badge>,
    },
    actionsColumn<MCPServer>([rowAction.edit((s) => setEditing(s)), { label: t('Detach'), icon: <UnplugIcon />, onClick: (s) => detach.mutate(s.id) }]),
  ]

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3 rounded-xl border bg-card p-3 shadow-xs">
        {isAdmin && (
          <>
            <FormField label={t('Attach a server')} className="min-w-64 flex-1">
              <OptionCombobox
                value={pick}
                onChange={setPick}
                options={free.map(mcpOption)}
                placeholder={free.length ? t('Select an MCP server') : t('Nothing left to attach')}
                disabled={!free.length}
              />
            </FormField>
            <Button disabled={!pick || attach.isPending} onClick={() => attach.mutate(Number(pick))}>
              {attach.isPending ? <Spinner /> : <PlugIcon />} {t('Attach')}
            </Button>
          </>
        )}
        <Button variant={isAdmin ? 'outline' : 'default'} className={isAdmin ? undefined : 'ml-auto'} onClick={() => setEditing('new')}>
          <PlusIcon /> {t('New MCP server')}
        </Button>
      </div>
      <DataTable
        columns={columns}
        data={attached.data}
        loading={attached.isLoading}
        error={attached.error}
        empty={{ icon: PlugIcon, title: t('No MCP servers attached'), description: t('Create servers on the MCP servers page, then attach them here.') }}
        searchPlaceholder={t('Search attached servers…')}
        getRowId={(s) => String(s.id)}
        onRowClick={(s) => setEditing(s)}
      />
      <McpDialog editing={editing} onClose={() => setEditing(null)} agentId={agent.id} />
    </div>
  )
}

function VersionsTab({ agent }: { agent: Agent }) {
  const tokens = useTokens(agent.id)
  const q = useQuery({ queryKey: ['versions', agent.id], queryFn: () => api.versions(agent.id), staleTime: 0 })
  const [viewing, setViewing] = useState<{ number: number; tab: 'overview' | 'changes' } | null>(null)
  const [rollbackTo, setRollbackTo] = useState<number | null>(null)
  const [comment, setComment] = useState('')
  const rollback = useAction(() => api.rollback(agent.id, rollbackTo!, comment), {
    invalidate: ['versions', 'agent', 'agents', 'agent-mcp', 'diff', 'version'],
    success: (v) => t('Rolled back; recorded as version {number}', { number: v.number }),
    onSuccess: () => {
      setRollbackTo(null)
      setViewing(null)
      setComment('')
    },
  })
  const latest = q.data?.[0]?.number

  const columns: ColumnDef<AgentVersion>[] = [
    {
      accessorKey: 'number',
      meta: { label: t('Version') },
      header: ({ column }) => <SortHeader column={column} title={t('Version')} />,
      cell: ({ row }) => (
        <span className="flex items-center gap-2 value-mono">
          {row.original.number} {row.original.number === latest && <Badge>{t('latest')}</Badge>}
        </span>
      ),
      size: 130,
    },
    {
      accessorKey: 'comment',
      meta: { label: t('Comment') },
      header: t('Comment'),
      cell: ({ getValue }) => getValue<string | null>() ?? <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'token',
      meta: { label: t('By token') },
      accessorFn: (v) => v.created_by_token_id,
      header: t('By token'),
      cell: ({ getValue }) => {
        const tokenId = getValue<number | null>()
        return tokenId == null ? <span className="text-muted-foreground">—</span> : <span>{tokens.data?.find((tk) => tk.id === tokenId)?.name ?? t('Token {id}', { id: tokenId })}</span>
      },
    },
    createdColumn<AgentVersion>(t('When')),
    {
      id: 'actions',
      enableHiding: false,
      header: () => <span className="sr-only">{t('Actions')}</span>,
      cell: ({ row }) => {
        const n = row.original.number
        const isLatest = n === latest
        return (
          <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
            <Button variant="outline" size="xs" aria-label={t('View version {number}', { number: n })} onClick={() => setViewing({ number: n, tab: 'overview' })}>
              <EyeIcon /> {t('View')}
            </Button>
            <Button variant="outline" size="xs" aria-label={t('Compare version {number}', { number: n })} disabled={isLatest} onClick={() => setViewing({ number: n, tab: 'changes' })}>
              <GitCompareIcon /> {t('Compare')}
            </Button>
            <Button size="xs" aria-label={t('Roll back to version {number}', { number: n })} disabled={isLatest} onClick={() => setRollbackTo(n)}>
              <RotateCcwIcon /> {t('Roll back')}
            </Button>
          </div>
        )
      },
    },
  ]

  return (
    <>
      <DataTable
        columns={columns}
        data={q.data}
        loading={q.isLoading}
        error={q.error}
        onRetry={() => q.refetch()}
        empty={{ icon: HistoryIcon, title: t('No versions recorded yet') }}
        searchPlaceholder={t('Search versions…')}
        initialSorting={[{ id: 'number', desc: true }]}
        getRowId={(v) => String(v.number)}
        onRowClick={(v) => setViewing({ number: v.number, tab: 'overview' })}
      />
      <VersionViewer
        agentId={agent.id}
        versions={q.data ?? []}
        number={viewing?.number ?? null}
        initialTab={viewing?.tab}
        onNumberChange={(n) => setViewing({ number: n, tab: viewing?.tab ?? 'overview' })}
        onClose={() => setViewing(null)}
        onRollback={setRollbackTo}
      />
      <FormDialog
        open={rollbackTo !== null}
        onClose={() => setRollbackTo(null)}
        title={t('Roll back to version {number}?', { number: rollbackTo ?? '' })}
        description={t('The agent becomes what that version was and the rollback is recorded as a new version, so nothing is lost. Shared models and MCP servers are never edited; copies are created when they changed.')}
        size="sm"
        submitLabel={t('Roll back')}
        onSubmit={() => rollback.mutate(undefined)}
        pending={rollback.isPending}
      >
        <FormField label={t('Comment (optional)')}>
          <Input value={comment} onChange={(e) => setComment(e.target.value)} placeholder={t('Why')} />
        </FormField>
      </FormDialog>
    </>
  )
}

export default function AgentDetail() {
  const { isAdmin, agentId: ownAgent } = useAuth()
  const id = Number(useParams().id)
  const agent = useQuery({ queryKey: ['agent', id], queryFn: () => api.agent(id), enabled: Number.isInteger(id) })
  const [editing, setEditing] = useState(false)
  // below admin an agent page is the own agent's (the service refuses the rest too)
  if (!isAdmin && ownAgent !== undefined && id !== ownAgent) return <Navigate to={`/agents/${ownAgent}`} replace />

  return (
    <Page>
      {isAdmin && (
        <Link to="/agents" className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeftIcon className="size-4" /> {t('Agents')}
        </Link>
      )}
      {agent.isError ? (
        <ErrorBox error={agent.error} onRetry={() => agent.refetch()} />
      ) : !agent.data ? (
        <LoadingRows rows={5} />
      ) : (
        <>
          <PageHeader
            title={agent.data.name}
            description={t('Agent {id}, created {date}', { id: agent.data.id, date: fmtDate(agent.data.timestamp) })}
            actions={
              <>
                <Button size="sm" onClick={() => setEditing(true)}>
                  <PencilIcon /> {t('Edit')}
                </Button>
                <Button variant="outline" size="sm" nativeButton={false} render={<Link to={`/rag?agent=${id}`} />}>
                  <BookOpenIcon /> {t('Knowledge base')}
                </Button>
                <Button variant="outline" size="sm" nativeButton={false} render={<Link to={`/memories?agent=${id}`} />}>
                  <BrainIcon /> {t('Memories')}
                </Button>
              </>
            }
          />
          <Tabs defaultValue="settings" className="min-h-0 flex-1 gap-3">
            <TabsList>
              <TabsTrigger value="settings">{t('Settings')}</TabsTrigger>
              <TabsTrigger value="mcp">
                <PlugIcon /> {t('MCP servers')}
              </TabsTrigger>
              <TabsTrigger value="versions">
                <HistoryIcon /> {t('Versions')}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="settings" className="min-h-0 flex-1 overflow-auto">
              <SettingsTab agent={agent.data} />
            </TabsContent>
            <TabsContent value="mcp" className="flex min-h-0 flex-1 flex-col">
              <McpTab agent={agent.data} />
            </TabsContent>
            <TabsContent value="versions" className="flex min-h-0 flex-1 flex-col">
              <VersionsTab agent={agent.data} />
            </TabsContent>
          </Tabs>
          <AgentDialog key={editing ? 'open' : 'closed'} mode={editing ? { kind: 'edit', agent: agent.data } : null} onClose={() => setEditing(false)} />
        </>
      )}
    </Page>
  )
}

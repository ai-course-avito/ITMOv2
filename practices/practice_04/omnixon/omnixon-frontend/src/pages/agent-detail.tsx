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
    { invalidate: ['agent', 'agents', 'versions', 'self-agent'], success: 'Agent saved' },
  )
  const problem = validateDraft(draft)
  const conflict = save.error instanceof ApiError && save.error.status === 409

  return (
    <div className="grid gap-4">
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Name, prompt and model</CardTitle>
            <CardDescription>What the agent is.</CardDescription>
          </CardHeader>
          <CardContent>
            <AgentBasics draft={draft} onChange={setDraft} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
            <CardDescription>How the agent works. Empty limits use the service defaults.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6">
            <AgentSettings draft={draft} onChange={setDraft} />
            <AgentComment draft={draft} onChange={setDraft} />
          </CardContent>
        </Card>
      </div>
      {problem && <p className="text-sm text-destructive">{problem}</p>}
      {conflict && <p className="text-sm text-destructive">The agent changed since you opened it. Reload the page to see the latest version, then apply your edit again.</p>}
      <div className="flex items-center gap-2">
        <Button disabled={!!problem || save.isPending || versions.isLoading} onClick={() => save.mutate(undefined)}>
          {save.isPending && <Spinner />} Save changes
        </Button>
        <Button variant="outline" onClick={() => setDraft(draftFrom(agent))}>
          Reset
        </Button>
        {latest !== undefined && <span className="text-xs text-muted-foreground">Based on version {latest}</span>}
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
  const attach = useAction((mcp: number) => api.attachMcpServer(agent.id, mcp), { invalidate: refresh, success: 'Attached', onSuccess: () => setPick(null) })
  const detach = useAction((mcp: number) => api.detachMcpServer(agent.id, mcp), { invalidate: refresh, success: 'Detached' })
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
      meta: { label: 'Transport' },
      accessorFn: (s) => String(s.config.transport ?? 'streamable_http'),
      header: 'Transport',
      cell: ({ getValue }) => <Badge variant="secondary">{getValue<string>()}</Badge>,
    },
    actionsColumn<MCPServer>([rowAction.edit((s) => setEditing(s)), { label: 'Detach', icon: <UnplugIcon />, onClick: (s) => detach.mutate(s.id) }]),
  ]

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3 rounded-xl border bg-card p-3 shadow-xs">
        {isAdmin && (
          <>
            <FormField label="Attach a server" className="min-w-64 flex-1">
              <OptionCombobox
                value={pick}
                onChange={setPick}
                options={free.map(mcpOption)}
                placeholder={free.length ? 'Select an MCP server' : 'Nothing left to attach'}
                disabled={!free.length}
              />
            </FormField>
            <Button disabled={!pick || attach.isPending} onClick={() => attach.mutate(Number(pick))}>
              {attach.isPending ? <Spinner /> : <PlugIcon />} Attach
            </Button>
          </>
        )}
        <Button variant={isAdmin ? 'outline' : 'default'} className={isAdmin ? undefined : 'ml-auto'} onClick={() => setEditing('new')}>
          <PlusIcon /> New MCP server
        </Button>
      </div>
      <DataTable
        columns={columns}
        data={attached.data}
        loading={attached.isLoading}
        error={attached.error}
        empty={{ icon: PlugIcon, title: 'No MCP servers attached', description: 'Create servers on the MCP servers page, then attach them here.' }}
        searchPlaceholder="Search attached servers…"
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
    success: (v) => `Rolled back; recorded as version ${v.number}`,
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
      meta: { label: 'Version' },
      header: ({ column }) => <SortHeader column={column} title="Version" />,
      cell: ({ row }) => (
        <span className="flex items-center gap-2 value-mono">
          {row.original.number} {row.original.number === latest && <Badge>latest</Badge>}
        </span>
      ),
      size: 130,
    },
    {
      accessorKey: 'comment',
      meta: { label: 'Comment' },
      header: 'Comment',
      cell: ({ getValue }) => getValue<string | null>() ?? <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'token',
      meta: { label: 'By token' },
      accessorFn: (v) => v.created_by_token_id,
      header: 'By token',
      cell: ({ getValue }) => {
        const tokenId = getValue<number | null>()
        return tokenId == null ? <span className="text-muted-foreground">—</span> : <span>{tokens.data?.find((t) => t.id === tokenId)?.name ?? `Token ${tokenId}`}</span>
      },
    },
    createdColumn<AgentVersion>('When'),
    {
      id: 'actions',
      enableHiding: false,
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => {
        const n = row.original.number
        const isLatest = n === latest
        return (
          <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
            <Button variant="outline" size="xs" aria-label={`View version ${n}`} onClick={() => setViewing({ number: n, tab: 'overview' })}>
              <EyeIcon /> View
            </Button>
            <Button variant="outline" size="xs" aria-label={`Compare version ${n}`} disabled={isLatest} onClick={() => setViewing({ number: n, tab: 'changes' })}>
              <GitCompareIcon /> Compare
            </Button>
            <Button size="xs" aria-label={`Roll back to version ${n}`} disabled={isLatest} onClick={() => setRollbackTo(n)}>
              <RotateCcwIcon /> Roll back
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
        empty={{ icon: HistoryIcon, title: 'No versions recorded yet' }}
        searchPlaceholder="Search versions…"
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
        title={`Roll back to version ${rollbackTo}?`}
        description="The agent becomes what that version was and the rollback is recorded as a new version, so nothing is lost. Shared models and MCP servers are never edited; copies are created when they changed."
        size="sm"
        submitLabel="Roll back"
        onSubmit={() => rollback.mutate(undefined)}
        pending={rollback.isPending}
      >
        <FormField label="Comment (optional)">
          <Input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Why" />
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
          <ArrowLeftIcon className="size-4" /> Agents
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
            description={`Agent ${agent.data.id}, created ${fmtDate(agent.data.timestamp)}`}
            actions={
              <>
                <Button size="sm" onClick={() => setEditing(true)}>
                  <PencilIcon /> Edit
                </Button>
                <Button variant="outline" size="sm" nativeButton={false} render={<Link to={`/rag?agent=${id}`} />}>
                  <BookOpenIcon /> Knowledge base
                </Button>
                <Button variant="outline" size="sm" nativeButton={false} render={<Link to={`/memories?agent=${id}`} />}>
                  <BrainIcon /> Memories
                </Button>
              </>
            }
          />
          <Tabs defaultValue="settings" className="min-h-0 flex-1 gap-3">
            <TabsList>
              <TabsTrigger value="settings">Settings</TabsTrigger>
              <TabsTrigger value="mcp">
                <PlugIcon /> MCP servers
              </TabsTrigger>
              <TabsTrigger value="versions">
                <HistoryIcon /> Versions
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

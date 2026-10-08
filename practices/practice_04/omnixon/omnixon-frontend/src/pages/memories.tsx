import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { BrainIcon, PlusIcon, SearchIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { actionsColumn, createdColumn, DataTable, idColumn, rowAction, SortHeader } from '@/components/data-table'
import { ConfirmDialog, FormDialog } from '@/components/dialogs'
import { FormField } from '@/components/form'
import { AgentField } from '@/components/agent-field'
import { UserSuggest } from '@/components/user-suggest'
import { EmptyState, LoadingRows, Page, PageHeader, QueryBar } from '@/components/page'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useAgents, useCurrentAgentId } from '@/lib/data'
import { useAction } from '@/lib/queries'
import type { Memory } from '@/lib/types'

// the agent's name is part of the row: the table caches cell values per row (see agents.tsx)
type Row = Memory & { agentName: string }

function MemoryDialog({ userId, agentId, agentName, editing, onClose }: { userId: string; agentId?: number; agentName?: string; editing: Memory | 'new' | null; onClose: () => void }) {
  const open = editing !== null
  const id = editing && editing !== 'new' ? editing.id : null
  const fresh = useQuery({ queryKey: ['memory', id], queryFn: () => api.memory(id!), enabled: open && id !== null })
  const [content, setContent] = useState('')
  useEffect(() => {
    if (!open) return
    setContent(editing === 'new' ? '' : (fresh.data?.content ?? ''))
  }, [open, editing, fresh.data])

  const save = useAction(
    () => (id === null ? api.createMemory({ user_id: userId, content: content.trim(), agent_id: agentId }) : api.updateMemory(id, content.trim())),
    { invalidate: ['memories', 'memory'], success: id === null ? 'Memory saved' : 'Memory updated', onSuccess: onClose },
  )
  return (
    <FormDialog
      open={open}
      onClose={onClose}
      title={id === null ? 'New memory' : `Memory ${id}`}
      description={`A lasting fact about ${userId}${agentName ? ` for agent “${agentName}”` : ''}. It is embedded for search each time it is saved. The user and agent of a memory cannot be changed.`}
      size="sm"
      onSubmit={() => save.mutate(undefined)}
      submitDisabled={!content.trim()}
      pending={save.isPending}
    >
      {id !== null && fresh.isLoading ? (
        <LoadingRows rows={2} />
      ) : (
        <FormField label="Fact">
          <Textarea rows={4} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Prefers short answers" />
        </FormField>
      )}
    </FormDialog>
  )
}

export default function Memories() {
  const [params, setParams] = useSearchParams()
  const agents = useAgents()
  const { isAdmin } = useAuth()
  const ownAgentId = useCurrentAgentId()
  const agentId = (isAdmin ? Number(params.get('agent')) : 0) || ownAgentId
  const [userInput, setUserInput] = useState(params.get('user') ?? '')
  const [user, setUser] = useState(params.get('user') ?? '')
  const [queryInput, setQueryInput] = useState('')
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState('100')
  const [editing, setEditing] = useState<Memory | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Memory | null>(null)

  const list = useQuery({
    queryKey: ['memories', user, agentId, limit, query],
    queryFn: () => api.memories(user, agentId, Number(limit) || 100, query || undefined),
    enabled: user !== '' && agentId !== undefined,
  })
  const rows = useMemo<Row[] | undefined>(
    () => list.data?.map((m) => ({ ...m, agentName: agents.data?.find((a) => a.id === m.agent_id)?.name ?? `Agent ${m.agent_id}` })),
    [list.data, agents.data],
  )
  const del = useAction((id: number) => api.deleteMemory(id), { invalidate: ['memories', 'memory'], success: 'Memory deleted', onSuccess: () => setDeleting(null) })

  useEffect(() => {
    const u = params.get('user')
    if (u) {
      setUserInput(u)
      setUser(u)
    }
  }, [params])

  const columns: ColumnDef<Row>[] = [
    idColumn<Row>(),
    { accessorKey: 'content', meta: { label: 'Fact' }, header: 'Fact', cell: ({ getValue }) => <span className="block max-w-3xl whitespace-normal">{getValue<string>()}</span> },
    {
      accessorKey: 'agentName',
      meta: { label: 'Agent' },
      header: ({ column }) => <SortHeader column={column} title="Agent" />,
      cell: ({ row }) => (
        <Link to={`/agents/${row.original.agent_id}`} className="underline-offset-4 hover:underline" onClick={(e) => e.stopPropagation()}>
          {row.original.agentName}
        </Link>
      ),
    },
    createdColumn<Row>('Saved'),
    actionsColumn<Row>([rowAction.edit((m) => setEditing(m)), rowAction.remove((m) => setDeleting(m))]),
  ]

  return (
    <Page>
      <PageHeader
        title="Memories"
        description="Facts the model remembers per (user, agent). Search is by meaning first, then by words."
        actions={
          <Button disabled={!user || agentId === undefined} onClick={() => setEditing('new')}>
            <PlusIcon /> New memory
          </Button>
        }
      />
      <QueryBar
        onSubmit={() => {
          setUser(userInput.trim())
          setQuery(queryInput.trim())
        }}
        actions={
          <Button type="submit" disabled={!userInput.trim()}>
            <SearchIcon /> {queryInput.trim() ? 'Search' : 'List'}
          </Button>
        }
      >
        <FormField label="User (external id)" className="w-64">
          <UserSuggest value={userInput} onChange={setUserInput} />
        </FormField>
        <AgentField
          className="w-64"
          agentId={agentId}
          onChange={(v) =>
            setParams((p) => {
              p.set('agent', v)
              return p
            })
          }
        />
        <FormField label="Search by meaning (optional)" className="min-w-64 flex-1">
          <Input value={queryInput} onChange={(e) => setQueryInput(e.target.value)} placeholder="what does the user drink?" />
        </FormField>
        <FormField label="Limit" className="w-24">
          <Input type="number" min={1} max={1000} value={limit} onChange={(e) => setLimit(e.target.value)} />
        </FormField>
      </QueryBar>

      {!user ? (
        <EmptyState icon={BrainIcon} title="Enter a user" description="Then you can see, search and edit what the model remembers about them." className="flex-1" />
      ) : (
        <DataTable
          columns={columns}
          data={rows}
          loading={list.isLoading || (list.isFetching && !list.data)}
          error={list.error}
          onRetry={() => list.refetch()}
          empty={{ icon: BrainIcon, title: query ? 'Nothing remembered for this query' : 'Nothing remembered yet' }}
          searchPlaceholder="Filter these memories…"
          getRowId={(m) => String(m.id)}
          onRowClick={(m) => setEditing(m)}
        />
      )}
      <MemoryDialog key={editing === 'new' ? 'new' : (editing?.id ?? 'none')} userId={user} agentId={agentId} agentName={agents.data?.find((a) => a.id === (editing !== null && editing !== 'new' ? editing.agent_id : agentId))?.name} editing={editing} onClose={() => setEditing(null)} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Forget memory ${deleting?.id}?`}
        description={deleting?.content}
        confirmLabel="Forget"
        pending={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting.id)}
      />
    </Page>
  )
}

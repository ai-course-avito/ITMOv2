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
import { t } from '@/lib/i18n'
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
    { invalidate: ['memories', 'memory'], success: id === null ? t('Memory saved') : t('Memory updated'), onSuccess: onClose },
  )
  return (
    <FormDialog
      open={open}
      onClose={onClose}
      title={id === null ? t('New memory') : t('Memory {id}', { id })}
      description={
        agentName
          ? t('A lasting fact about {user} for agent “{agent}”. It is embedded for search each time it is saved. The user and agent of a memory cannot be changed.', { user: userId, agent: agentName })
          : t('A lasting fact about {user}. It is embedded for search each time it is saved. The user and agent of a memory cannot be changed.', { user: userId })
      }
      size="sm"
      onSubmit={() => save.mutate(undefined)}
      submitDisabled={!content.trim()}
      pending={save.isPending}
    >
      {id !== null && fresh.isLoading ? (
        <LoadingRows rows={2} />
      ) : (
        <FormField label={t('Fact')}>
          <Textarea rows={4} value={content} onChange={(e) => setContent(e.target.value)} placeholder={t('Prefers short answers')} />
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
    () => list.data?.map((m) => ({ ...m, agentName: agents.data?.find((a) => a.id === m.agent_id)?.name ?? t('Agent {id}', { id: m.agent_id }) })),
    [list.data, agents.data],
  )
  const del = useAction((id: number) => api.deleteMemory(id), { invalidate: ['memories', 'memory'], success: t('Memory deleted'), onSuccess: () => setDeleting(null) })

  useEffect(() => {
    const u = params.get('user')
    if (u) {
      setUserInput(u)
      setUser(u)
    }
  }, [params])

  const columns: ColumnDef<Row>[] = [
    idColumn<Row>(),
    { accessorKey: 'content', meta: { label: t('Fact') }, header: t('Fact'), cell: ({ getValue }) => <span className="block max-w-3xl whitespace-normal">{getValue<string>()}</span> },
    {
      accessorKey: 'agentName',
      meta: { label: t('Agent') },
      header: ({ column }) => <SortHeader column={column} title={t('Agent')} />,
      cell: ({ row }) => (
        <Link to={`/agents/${row.original.agent_id}`} className="underline-offset-4 hover:underline" onClick={(e) => e.stopPropagation()}>
          {row.original.agentName}
        </Link>
      ),
    },
    createdColumn<Row>(t('Saved')),
    actionsColumn<Row>([rowAction.edit((m) => setEditing(m)), rowAction.remove((m) => setDeleting(m))]),
  ]

  return (
    <Page>
      <PageHeader
        title={t('Memories')}
        description={t('Facts the model remembers per (user, agent). Search is by meaning first, then by words.')}
        actions={
          <Button disabled={!user || agentId === undefined} onClick={() => setEditing('new')}>
            <PlusIcon /> {t('New memory')}
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
            <SearchIcon /> {queryInput.trim() ? t('Search') : t('List')}
          </Button>
        }
      >
        <FormField label={t('User (external id)')} className="w-64">
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
        <FormField label={t('Search by meaning (optional)')} className="min-w-64 flex-1">
          <Input value={queryInput} onChange={(e) => setQueryInput(e.target.value)} placeholder={t('what does the user drink?')} />
        </FormField>
        <FormField label={t('Limit')} className="w-24">
          <Input type="number" min={1} max={1000} value={limit} onChange={(e) => setLimit(e.target.value)} />
        </FormField>
      </QueryBar>

      {!user ? (
        <EmptyState icon={BrainIcon} title={t('Enter a user')} description={t('Then you can see, search and edit what the model remembers about them.')} className="flex-1" />
      ) : (
        <DataTable
          columns={columns}
          data={rows}
          loading={list.isLoading || (list.isFetching && !list.data)}
          error={list.error}
          onRetry={() => list.refetch()}
          empty={{ icon: BrainIcon, title: query ? t('Nothing remembered for this query') : t('Nothing remembered yet') }}
          searchPlaceholder={t('Filter these memories…')}
          getRowId={(m) => String(m.id)}
          onRowClick={(m) => setEditing(m)}
        />
      )}
      <MemoryDialog key={editing === 'new' ? 'new' : (editing?.id ?? 'none')} userId={user} agentId={agentId} agentName={agents.data?.find((a) => a.id === (editing !== null && editing !== 'new' ? editing.agent_id : agentId))?.name} editing={editing} onClose={() => setEditing(null)} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={t('Forget memory {id}?', { id: deleting?.id ?? '' })}
        description={deleting?.content}
        confirmLabel={t('Forget')}
        pending={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting.id)}
      />
    </Page>
  )
}

import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { ColumnDef } from '@tanstack/react-table'
import { BotIcon, PlusIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AgentDialog, type AgentDialogMode } from '@/components/agent-dialog'
import {
  actionsColumn,
  createdColumn,
  DataTable,
  idColumn,
  nameColumn,
  rowAction,
  SortHeader,
} from '@/components/data-table'
import { ConfirmDialog } from '@/components/dialogs'
import { Page, PageHeader } from '@/components/page'
import { api } from '@/lib/api'
import { modelName, useAgents, useModels, useSelfAgent } from '@/lib/data'
import { clip } from '@/lib/format'
import { useAction } from '@/lib/queries'
import type { Agent } from '@/lib/types'

// derived fields live in the data: the table caches cell values per row, so a lookup done
// inside a column would stay unresolved if the models arrive after the agents
type Row = Agent & { modelLabel: string }

export default function Agents() {
  const navigate = useNavigate()
  const agents = useAgents()
  const models = useModels()
  const self = useSelfAgent()
  const [dialog, setDialog] = useState<AgentDialogMode | null>(null)
  const [deleting, setDeleting] = useState<Agent | null>(null)
  const del = useAction((id: number) => api.deleteAgent(id), {
    invalidate: ['agents'],
    success: 'Agent deleted',
    onSuccess: () => setDeleting(null),
  })
  const rows = useMemo<Row[] | undefined>(
    () =>
      agents.data?.map((a) => ({
        ...a,
        modelLabel: models.data ? modelName(models.data.find((m) => m.id === a.model_id)?.request_json) : '…',
      })),
    [agents.data, models.data],
  )

  const columns: ColumnDef<Row>[] = [
    { ...idColumn<Row>(), size: 80 },
    {
      ...nameColumn<Row>((a) => `/agents/${a.id}`),
      cell: ({ row }) => (
        <span className="flex items-center gap-2">
          <Link
            to={`/agents/${row.original.id}`}
            className="font-medium underline-offset-4 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {row.original.name}
          </Link>
          {self.data?.id === row.original.id && <Badge variant="outline">yours</Badge>}
        </span>
      ),
    },
    {
      accessorKey: 'prompt',
      meta: { label: 'Prompt' },
      header: ({ column }) => <SortHeader column={column} title="Prompt" />,
      // no max-width: the column is as wide as the clipped text (a capped box let it run over the Model column)
      cell: ({ getValue }) => (
        <span className="text-muted-foreground" title={getValue<string>() || undefined}>
          {clip(getValue<string>()) || <em>empty prompt</em>}
        </span>
      ),
    },
    {
      accessorKey: 'modelLabel',
      meta: { label: 'Model' },
      header: ({ column }) => <SortHeader column={column} title="Model" />,
      cell: ({ row }) => (
        <Link
          to={`/models?open=${row.original.model_id}`}
          className="underline-offset-4 hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {row.original.modelLabel}
        </Link>
      ),
    },
    {
      id: 'tools',
      meta: { label: 'Tools' },
      accessorFn: (a) => (a.config.tools ?? ['rag', 'memory']).join(', '),
      header: 'Tools',
      cell: ({ row }) => (
        <span className="flex gap-1">
          {(row.original.config.tools ?? ['rag', 'memory']).map((t) => (
            <Badge key={t} variant="secondary">
              {t}
            </Badge>
          ))}
          {row.original.config.tools?.length === 0 && <span className="text-muted-foreground">none</span>}
        </span>
      ),
    },
    createdColumn<Row>(),
    actionsColumn<Row>([
      rowAction.open((a) => navigate(`/agents/${a.id}`)),
      rowAction.edit((a) => setDialog({ kind: 'edit', agent: a })),
      rowAction.duplicate((a) => setDialog({ kind: 'duplicate', agent: a })),
      rowAction.remove((a) => setDeleting(a)),
    ]),
  ]

  return (
    <Page>
      <PageHeader
        title="Agents"
        description="Every behaviour change is versioned. Open an agent to see its versions, compare them and roll back."
        actions={
          <Button onClick={() => setDialog({ kind: 'create' })}>
            <PlusIcon /> New agent
          </Button>
        }
      />
      <DataTable
        columns={columns}
        data={rows}
        loading={agents.isLoading}
        error={agents.error}
        onRetry={() => agents.refetch()}
        empty={{
          icon: BotIcon,
          title: 'No agents yet',
          description: 'An agent is a prompt, a model, tools and settings.',
        }}
        searchPlaceholder="Search agents…"
        getRowId={(a) => String(a.id)}
        onRowClick={(a) => navigate(`/agents/${a.id}`)}
      />
      <AgentDialog
        key={dialog ? `${dialog.kind}-${'agent' in dialog ? dialog.agent.id : 'new'}` : 'closed'}
        mode={dialog}
        onClose={() => setDialog(null)}
      />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete agent “${deleting?.name}”?`}
        description="Its knowledge base, memories and versions go with it. An agent used by a unit cannot be deleted (409)."
        pending={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting.id)}
      />
    </Page>
  )
}

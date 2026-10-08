import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { GlobeIcon, PlugIcon, PlusIcon, RadioIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FieldGroup, FieldSeparator } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { actionsColumn, createdColumn, DataTable, idColumn, nameColumn, rowAction, SortHeader } from '@/components/data-table'
import { ConfirmDialog, FormDialog } from '@/components/dialogs'
import { FormField, JsonEditor, OptionSelect } from '@/components/form'
import { LoadingRows, Page, PageHeader } from '@/components/page'
import { api } from '@/lib/api'
import { useMcpServers } from '@/lib/data'
import { parseJsonObject, pretty } from '@/lib/format'
import { useAction } from '@/lib/queries'
import { useOpenParam } from '@/lib/use-open-param'
import { MCP_OPTIONS, NAME_MAX, type MCPServer } from '@/lib/types'

function split(config: Record<string, unknown>) {
  const { url, transport, ...rest } = config
  return {
    url: typeof url === 'string' ? url : '',
    transport: transport === 'sse' ? 'sse' : 'streamable_http',
    rest: Object.keys(rest).length ? pretty(rest) : '',
  }
}

export type McpEditing = MCPServer | { copyOf: MCPServer } | 'new' | null
type Editing = McpEditing

/** Make or change an MCP server. With `agentId` a new server is attached to that agent at once (a user token's servers always are). */
export function McpDialog({ editing, onClose, agentId }: { editing: Editing; onClose: () => void; agentId?: number }) {
  const open = editing !== null
  const id = editing && editing !== 'new' && 'id' in editing ? editing.id : null
  const fresh = useQuery({ queryKey: ['mcp-server', id], queryFn: () => api.mcpServer(id!), enabled: open && id !== null })
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [transport, setTransport] = useState('streamable_http')
  const [rest, setRest] = useState('')

  useEffect(() => {
    if (!open) return
    const s = editing === 'new' ? split({}) : editing && 'copyOf' in editing ? split(editing.copyOf.config) : fresh.data ? split(fresh.data.config) : null
    if (s) {
      setName(editing === 'new' ? '' : editing && 'copyOf' in editing ? `${editing.copyOf.name} (copy)`.slice(0, NAME_MAX) : (fresh.data?.name ?? ''))
      setUrl(s.url)
      setTransport(s.transport)
      setRest(s.rest)
    }
  }, [open, editing, fresh.data])

  const parsed = parseJsonObject(rest)
  const save = useAction(
    (config: Record<string, unknown>) =>
      id === null
        ? api.createMcpServer(name.trim(), config, agentId)
        : api.updateMcpServer(id, { config, ...(name.trim() !== fresh.data?.name ? { name: name.trim() } : {}) }),
    {
      invalidate: ['mcp-servers', 'mcp-server', 'versions', 'agent-mcp'],
      success: id === null ? 'MCP server created' : 'MCP server updated',
      onSuccess: onClose,
    },
  )

  return (
    <FormDialog
      open={open}
      onClose={onClose}
      title={id === null ? 'New MCP server' : `MCP server “${fresh.data?.name ?? id}”`}
      description="An external tool server that agents can use."
      onSubmit={() => parsed.ok && save.mutate({ ...parsed.value, url: url.trim(), transport })}
      submitDisabled={!url.trim() || !name.trim() || !parsed.ok}
      pending={save.isPending}
    >
      {id !== null && fresh.isLoading ? (
        <LoadingRows rows={3} />
      ) : (
        <FieldGroup>
          <FormField label="Name">
            <Input maxLength={NAME_MAX} value={name} onChange={(e) => setName(e.target.value)} placeholder="Calculator" />
          </FormField>
          <FormField label="URL">
            <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://mcp-server:8000/mcp" />
          </FormField>
          <FormField label="Transport">
            <OptionSelect
              value={transport}
              onChange={setTransport}
              options={[
                { value: 'streamable_http', label: 'streamable_http', icon: GlobeIcon, description: 'Plain HTTP requests, the usual choice' },
                { value: 'sse', label: 'sse', icon: RadioIcon, description: 'A long-lived server-sent-events connection' },
              ]}
            />
          </FormField>
          <FieldSeparator />
          <FormField label="Other options (JSON)" description={`Allowed keys: ${MCP_OPTIONS.join(', ')}.`}>
            <JsonEditor value={rest} onChange={setRest} rows={6} placeholder={'{\n  "headers": {"Authorization": "Bearer …"},\n  "timeout": 5\n}'} />
          </FormField>
          {id !== null && <p className="text-xs text-muted-foreground">Saving records a new version of every agent that has this server attached.</p>}
        </FieldGroup>
      )}
    </FormDialog>
  )
}

export default function McpServers() {
  const servers = useMcpServers()
  const [editing, setEditing] = useState<Editing>(null)
  const [deleting, setDeleting] = useState<MCPServer | null>(null)
  useOpenParam(servers.data, setEditing)
  const del = useAction((id: number) => api.deleteMcpServer(id), {
    invalidate: ['mcp-servers', 'versions', 'agent-mcp'],
    success: 'MCP server deleted',
    onSuccess: () => setDeleting(null),
  })

  const columns: ColumnDef<MCPServer>[] = [
    { ...idColumn<MCPServer>(), size: 80 },
    nameColumn<MCPServer>(),
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
      header: ({ column }) => <SortHeader column={column} title="Transport" />,
      cell: ({ getValue }) => <Badge variant="secondary">{getValue<string>()}</Badge>,
    },
    {
      id: 'options',
      meta: { label: 'Options' },
      accessorFn: (s) => Object.keys(s.config).filter((k) => k !== 'url' && k !== 'transport').join(', '),
      header: 'Options',
      cell: ({ getValue }) => <span className="text-muted-foreground">{getValue<string>() || '—'}</span>,
    },
    createdColumn<MCPServer>(),
    actionsColumn<MCPServer>([
      rowAction.edit((s) => setEditing(s)),
      rowAction.duplicate((s) => setEditing({ copyOf: s })),
      rowAction.remove((s) => setDeleting(s)),
    ]),
  ]

  return (
    <Page>
      <PageHeader
        title="MCP servers"
        description="External tool servers. Attach them to agents on the agent's page. A dead server is skipped automatically at request time."
        actions={
          <Button onClick={() => setEditing('new')}>
            <PlusIcon /> New server
          </Button>
        }
      />
      <DataTable
        columns={columns}
        data={servers.data}
        loading={servers.isLoading}
        error={servers.error}
        onRetry={() => servers.refetch()}
        empty={{ icon: PlugIcon, title: 'No MCP servers yet', description: 'Tool servers an agent may call.' }}
        searchPlaceholder="Search servers…"
        getRowId={(s) => String(s.id)}
        onRowClick={(s) => setEditing(s)}
      />
      <McpDialog editing={editing} onClose={() => setEditing(null)} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete MCP server “${deleting?.name}”?`}
        description="It is detached from every agent that uses it (each gets a new version)."
        pending={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting.id)}
      />
    </Page>
  )
}

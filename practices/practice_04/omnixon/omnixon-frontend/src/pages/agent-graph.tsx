import { useCallback, useEffect, useMemo, useState } from 'react'
import dagre from '@dagrejs/dagre'
import {
  Background,
  BackgroundVariant,
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  Handle,
  MarkerType,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useTheme } from 'next-themes'
import { BotIcon, LayoutGridIcon, PlusIcon, Trash2Icon, WorkflowIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { BaseNode, BaseNodeContent, BaseNodeHeader, BaseNodeHeaderTitle } from '@/components/base-node'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FieldGroup } from '@/components/ui/field'
import { Textarea } from '@/components/ui/textarea'
import { ConfirmDialog, FormDialog } from '@/components/dialogs'
import { FormField, OptionCombobox } from '@/components/form'
import { EmptyState, LoadingRows, Page, PageHeader } from '@/components/page'
import { api } from '@/lib/api'
import { modelName, useAgentConnections, useAgents, useModels } from '@/lib/data'
import { clip } from '@/lib/format'
import { agentOption } from '@/lib/options'
import { useAction } from '@/lib/queries'
import type { Agent, AgentConnection } from '@/lib/types'

const NODE_W = 240
const NODE_H = 88
const DESCRIPTION_MAX = 1000

type AgentNodeData = { agent: Agent; model: string }
type AgentFlowNode = Node<AgentNodeData, 'agent'>
type ConnectionFlowEdge = Edge<{ connection: AgentConnection }, 'connection'>

/** Left to right in the direction of the calls; agents without connections are laid out too. */
function arrange(agents: Agent[], connections: AgentConnection[]): Record<number, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 40, ranksep: 260, marginx: 20, marginy: 20 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const a of agents) g.setNode(String(a.id), { width: NODE_W, height: NODE_H })
  for (const c of connections) g.setEdge(String(c.agent1_id), String(c.agent2_id))
  dagre.layout(g)
  return Object.fromEntries(
    agents.map((a) => {
      const p = g.node(String(a.id))
      return [a.id, { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 }]
    }),
  )
}

function AgentNode({ data }: NodeProps<AgentFlowNode>) {
  return (
    <BaseNode className="w-60 shadow-sm" data-testid={`agent-node-${data.agent.id}`}>
      <Handle
        type="target"
        position={Position.Left}
        className="!size-2.5 !border-2 !border-background !bg-muted-foreground"
      />
      <BaseNodeHeader className="border-b">
        <BotIcon className="size-4 shrink-0 text-muted-foreground" />
        <BaseNodeHeaderTitle className="truncate text-sm">{data.agent.name}</BaseNodeHeaderTitle>
        <span className="value-mono text-xs text-muted-foreground">{data.agent.id}</span>
      </BaseNodeHeader>
      <BaseNodeContent className="gap-y-1.5 py-2">
        <p className="truncate text-xs text-muted-foreground" title={data.agent.prompt || undefined}>
          {clip(data.agent.prompt) || <em>empty prompt</em>}
        </p>
        <Badge variant="secondary" className="max-w-full truncate font-mono text-[11px]">
          {data.model}
        </Badge>
      </BaseNodeContent>
      <Handle
        type="source"
        position={Position.Right}
        className="!size-2.5 !border-2 !border-background !bg-foreground"
      />
    </BaseNode>
  )
}

function ConnectionEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  selected,
  data,
}: EdgeProps<ConnectionFlowEdge>) {
  const [path, labelX, labelY] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition })
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={{ strokeWidth: selected ? 2 : 1.5, stroke: 'var(--muted-foreground)' }}
      />
      {data && (
        <EdgeLabelRenderer>
          <div
            className="nodrag nopan pointer-events-auto absolute max-w-52 cursor-pointer truncate rounded-md border bg-background px-2 py-0.5 text-xs text-muted-foreground shadow-xs hover:text-foreground"
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
            title={data.connection.description}
            data-testid={`edge-label-${data.connection.id}`}
          >
            {clip(data.connection.description, 30)}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

const nodeTypes = { agent: AgentNode }
const edgeTypes = { connection: ConnectionEdge }

type Editing = AgentConnection | { agent1?: number; agent2?: number } | null

/** Make a connection (`{agent1?, agent2?}`: what is chosen already) or change / delete one. */
function ConnectionDialog({ editing, agents, onClose }: { editing: Editing; agents: Agent[]; onClose: () => void }) {
  const existing = editing && 'id' in editing ? editing : null
  const [agent1, setAgent1] = useState('')
  const [agent2, setAgent2] = useState('')
  const [description, setDescription] = useState('')
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (!editing) return
    if ('id' in editing) {
      setAgent1(String(editing.agent1_id))
      setAgent2(String(editing.agent2_id))
      setDescription(editing.description)
    } else {
      setAgent1(editing.agent1 !== undefined ? String(editing.agent1) : '')
      setAgent2(editing.agent2 !== undefined ? String(editing.agent2) : '')
      setDescription('')
    }
  }, [editing])

  const invalidate = ['agent-connections', 'versions']
  const save = useAction(
    () =>
      existing
        ? api.updateAgentConnection(existing.id, description.trim())
        : api.createAgentConnection(Number(agent1), Number(agent2), description.trim()),
    { invalidate, success: existing ? 'Connection updated' : 'Connection created', onSuccess: onClose },
  )
  const remove = useAction(() => api.deleteAgentConnection(existing!.id), {
    invalidate,
    success: 'Connection deleted',
    onSuccess: () => {
      setDeleting(false)
      onClose()
    },
  })

  const options = agents.map((a) => agentOption(a))
  const name = (id: string) => agents.find((a) => String(a.id) === id)?.name ?? id
  const same = agent1 !== '' && agent1 === agent2
  return (
    <>
      <FormDialog
        open={editing !== null}
        onClose={onClose}
        title={existing ? `${name(agent1)} → ${name(agent2)}` : 'New connection'}
        description="The first agent may call the second one (tools list_agents and ask_agent). The description is what the first agent reads about the second."
        submitLabel={existing ? 'Save' : 'Connect'}
        onSubmit={() => save.mutate(undefined)}
        submitDisabled={!agent1 || !agent2 || same || !description.trim()}
        pending={save.isPending}
        problem={same ? 'An agent cannot be connected to itself.' : undefined}
        footerStart={
          existing && (
            <Button type="button" variant="outline" className="text-destructive" onClick={() => setDeleting(true)}>
              <Trash2Icon /> Delete
            </Button>
          )
        }
      >
        <FieldGroup>
          <FormField label="Calling agent">
            <OptionCombobox
              value={agent1}
              onChange={setAgent1}
              options={options}
              placeholder="Choose an agent"
              disabled={!!existing}
            />
          </FormField>
          <FormField label="Called agent">
            <OptionCombobox
              value={agent2}
              onChange={setAgent2}
              options={options}
              placeholder="Choose an agent"
              disabled={!!existing}
            />
          </FormField>
          <FormField label="Description" description="What the called agent is for, written for the calling agent.">
            <Textarea
              maxLength={DESCRIPTION_MAX}
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Knows the prices and the stock of every product"
            />
          </FormField>
        </FieldGroup>
      </FormDialog>
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title="Delete this connection?"
        description={`${name(agent1)} will no longer be able to call ${name(agent2)}. This is recorded as a version of ${name(agent1)}.`}
        pending={remove.isPending}
        onConfirm={() => remove.mutate(undefined)}
      />
    </>
  )
}

function Graph({
  agents,
  connections,
  modelOf,
}: {
  agents: Agent[]
  connections: AgentConnection[]
  modelOf: (a: Agent) => string
}) {
  const { resolvedTheme } = useTheme()
  const { fitView } = useReactFlow()
  const [editing, setEditing] = useState<Editing>(null)
  const [nodes, setNodes, onNodesChange] = useNodesState<AgentFlowNode>([])

  const layout = useCallback(() => {
    const at = arrange(agents, connections)
    setNodes(
      agents.map((a) => ({
        id: String(a.id),
        type: 'agent',
        position: at[a.id],
        data: { agent: a, model: modelOf(a) },
      })),
    )
    requestAnimationFrame(() => fitView({ padding: 0.2, duration: 200 }))
  }, [agents, connections, modelOf, setNodes, fitView])

  // the cards follow the data (a new agent, a renamed one); where a card stands is kept until "Arrange"
  const ids = agents.map((a) => a.id).join(',')
  const edgeIds = connections.map((c) => c.id).join(',')
  useEffect(() => {
    setNodes((current) => {
      if (current.length !== agents.length || current.map((n) => n.id).join(',') !== ids) return []
      return current.map((n) => {
        const agent = agents.find((a) => String(a.id) === n.id)!
        return { ...n, data: { agent, model: modelOf(agent) } }
      })
    })
  }, [agents, ids, modelOf, setNodes])
  useEffect(() => {
    if (nodes.length === 0 && agents.length) layout()
  }, [nodes.length, agents.length, layout, edgeIds])

  const edges: ConnectionFlowEdge[] = useMemo(
    () =>
      connections.map((c) => ({
        id: String(c.id),
        source: String(c.agent1_id),
        target: String(c.agent2_id),
        type: 'connection',
        data: { connection: c },
        markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18, color: 'var(--muted-foreground)' },
      })),
    [connections],
  )

  const onConnect = useCallback((c: Connection) => {
    if (c.source && c.target && c.source !== c.target)
      setEditing({ agent1: Number(c.source), agent2: Number(c.target) })
  }, [])

  return (
    <div
      className="relative min-h-[28rem] flex-1 overflow-hidden rounded-xl border bg-background"
      data-testid="agent-graph"
    >
      <ReactFlow<AgentFlowNode, ConnectionFlowEdge>
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onConnect={onConnect}
        onEdgeClick={(_, edge) => edge.data && setEditing(edge.data.connection)}
        colorMode={resolvedTheme === 'dark' ? 'dark' : 'light'}
        fitView
        minZoom={0.3}
        proOptions={{ hideAttribution: true }}
        nodesConnectable
        edgesFocusable
        deleteKeyCode={null}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1.2} color="var(--border)" />
        <Panel position="top-right" className="flex gap-2">
          <Button variant="outline" size="sm" onClick={layout}>
            <LayoutGridIcon /> Arrange
          </Button>
          <Button size="sm" onClick={() => setEditing({})}>
            <PlusIcon /> Add connection
          </Button>
        </Panel>
      </ReactFlow>
      <ConnectionDialog editing={editing} agents={agents} onClose={() => setEditing(null)} />
    </div>
  )
}

export default function AgentGraph() {
  const agents = useAgents()
  const models = useModels()
  const connections = useAgentConnections()
  const modelOf = useCallback(
    (a: Agent) => (models.data ? modelName(models.data.find((m) => m.id === a.model_id)?.request_json) : '…'),
    [models.data],
  )

  return (
    <Page>
      <PageHeader
        title="Agent graph"
        description={
          <>
            An arrow lets an agent call another one: it gets the tools <span className="value-mono">list_agents</span>{' '}
            and <span className="value-mono">ask_agent</span>. Drag from the right edge of a card to another card, or
            use Add connection; click an arrow to change or delete it. Agents are on the{' '}
            <Link to="/agents" className="underline underline-offset-4">
              Agents
            </Link>{' '}
            page.
          </>
        }
      />
      {!agents.data || !connections.data ? (
        <LoadingRows rows={6} />
      ) : agents.data.length < 2 ? (
        <EmptyState
          icon={WorkflowIcon}
          title="Two agents are needed"
          description="Make another agent to connect it to the first one."
        />
      ) : (
        <ReactFlowProvider>
          <Graph agents={agents.data} connections={connections.data} modelOf={modelOf} />
        </ReactFlowProvider>
      )}
    </Page>
  )
}

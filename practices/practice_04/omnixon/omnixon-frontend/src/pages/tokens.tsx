import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { ColumnDef } from '@tanstack/react-table'
import { AlertTriangleIcon, KeyRoundIcon, PlusIcon } from 'lucide-react'
import { ROLE_ICON } from '@/lib/roles'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FieldGroup } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import DecryptedText from '@/components/DecryptedText'
import { AgentField } from '@/components/agent-field'
import { actionsColumn, createdColumn, DataTable, idColumn, nameColumn, rowAction, SortHeader } from '@/components/data-table'
import { ConfirmDialog, FormDialog } from '@/components/dialogs'
import { CopyButton } from '@/components/display'
import { FormField, OptionSelect, type Option } from '@/components/form'
import { Page, PageHeader } from '@/components/page'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useAgents, useTokens } from '@/lib/data'
import { useAction } from '@/lib/queries'
import { NAME_MAX, ROLES, rankOf, type NewToken, type Role, type Token } from '@/lib/types'

/** The highest role each role may hand out. The service decides; this only keeps the panel from offering what it would refuse. */
const MAY_HAND_OUT: Record<Role, number> = { regular: 0, user: 2, admin: 2, owner: 4 }

const ROLE_HELP: Record<Role, string> = {
  regular: 'Requests, users and history of the agent: what a client (a bot, a site) needs.',
  user: 'Plus everything about the agent: prompt, knowledge base, MCP servers, memories, tokens for it.',
  admin: 'Plus every agent, models, every token up to user, usage of all, and acting as another agent.',
  owner: 'Plus tokens of any role, including admin and owner.',
}

const roleVariant = (role: Role) => (role === 'owner' ? 'default' : role === 'admin' ? 'secondary' : 'outline')

type Row = Token & { agentName: string }

/** Shown once: the secret of a token that was just made. It is not stored anywhere that can be read back. */
function SecretDialog({ made, onClose }: { made: NewToken | null; onClose: () => void }) {
  return (
    <FormDialog
      open={made !== null}
      onClose={onClose}
      title="Copy the token now"
      description={
        <span className="flex items-start gap-2">
          <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-warning" />
          <span>It is shown only here, once. Only a hash of it is kept, so it cannot be shown again; make a new token if it is lost.</span>
        </span>
      }
      size="md"
    >
      {made && (
        <div className="grid gap-3">
          <p className="text-sm text-muted-foreground">
            Token “{made.name}”, role <strong>{made.role}</strong>.
          </p>
          <div className="flex items-center gap-1 rounded-lg border bg-muted/40 p-2">
            <code className="value-mono min-w-0 flex-1 break-all text-sm">
              {/* the animation is for the eyes; the text for readers (and tests) is the plain secret */}
              <span aria-hidden>
                <DecryptedText text={made.token} animateOn="view" speed={30} maxIterations={8} />
              </span>
              <span data-testid="new-token" className="sr-only">
                {made.token}
              </span>
            </code>
            <CopyButton text={made.token} label="Copy token" />
          </div>
        </div>
      )}
    </FormDialog>
  )
}

export default function Tokens() {
  const { token: me, agentId: ownAgent, isAdmin } = useAuth()
  const agents = useAgents()
  const tokens = useTokens(ownAgent, true)
  const [creating, setCreating] = useState(false)
  const [renaming, setRenaming] = useState<Token | null>(null)
  const [deleting, setDeleting] = useState<Token | null>(null)
  const [made, setMade] = useState<NewToken | null>(null)

  const rows = useMemo<Row[] | undefined>(
    () => tokens.data?.map((t) => ({ ...t, agentName: agents.data?.find((a) => a.id === t.agent_id)?.name ?? `Agent ${t.agent_id}` })),
    [tokens.data, agents.data],
  )
  const manageable = (t: Token) => !!me && rankOf(t.role) <= MAY_HAND_OUT[me.role] && (isAdmin || t.agent_id === ownAgent)

  const del = useAction((t: Token) => api.deleteToken(t.id), { invalidate: ['tokens'], success: 'Token deleted', onSuccess: () => setDeleting(null) })

  const columns: ColumnDef<Row>[] = [
    { ...idColumn<Row>(), size: 80 },
    {
      ...nameColumn<Row>(),
      cell: ({ row }) => (
        <span className="flex items-center gap-2">
          <span className="font-medium">{row.original.name}</span>
          {row.original.id === me?.id && <Badge variant="outline">you</Badge>}
          {row.original.is_initial && <Badge variant="outline">initial</Badge>}
        </span>
      ),
    },
    {
      accessorKey: 'role',
      meta: { label: 'Role' },
      header: ({ column }) => <SortHeader column={column} title="Role" />,
      cell: ({ row }) => {
        const Icon = ROLE_ICON[row.original.role]
        return (
          <Badge variant={roleVariant(row.original.role)}>
            <Icon /> {row.original.role}
          </Badge>
        )
      },
    },
    {
      accessorKey: 'agentName',
      meta: { label: 'Agent' },
      header: ({ column }) => <SortHeader column={column} title="Agent" />,
      cell: ({ row }) =>
        me?.role === 'regular' ? (
          row.original.agentName
        ) : (
          <Link to={`/agents/${row.original.agent_id}`} className="underline-offset-4 hover:underline" onClick={(e) => e.stopPropagation()}>
            {row.original.agentName}
          </Link>
        ),
    },
    createdColumn<Row>(),
    actionsColumn<Row>([
      rowAction.edit((t) => setRenaming(t), (t) => !manageable(t)),
      rowAction.remove((t) => setDeleting(t), (t) => !manageable(t) || t.id === me?.id || t.is_initial),
    ]),
  ]

  return (
    <Page>
      <PageHeader
        title="Tokens"
        description={
          isAdmin
            ? 'Who may use an agent, and as what. Every token belongs to one agent and has a role; the secret is shown once, when it is made.'
            : 'Who may use your agent, and as what. The secret of a token is shown once, when it is made.'
        }
        actions={
          <Button onClick={() => setCreating(true)}>
            <PlusIcon /> New token
          </Button>
        }
      />
      <DataTable
        columns={columns}
        data={rows}
        loading={tokens.isLoading}
        error={tokens.error}
        onRetry={() => tokens.refetch()}
        empty={{ icon: KeyRoundIcon, title: 'No tokens', description: 'Make one to give a client access.' }}
        searchPlaceholder="Search tokens…"
        getRowId={(t) => String(t.id)}
        onRowClick={(t) => manageable(t) && setRenaming(t)}
      />
      <NewTokenDialog open={creating} onClose={() => setCreating(false)} onMade={(t) => { setCreating(false); setMade(t) }} />
      <EditDialog token={renaming} onClose={() => setRenaming(null)} />
      <SecretDialog made={made} onClose={() => setMade(null)} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete token “${deleting?.name}”?`}
        description="It stops working at once. Its usage statistics stay under its name."
        pending={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting)}
      />
    </Page>
  )
}

function NewTokenDialog({ open, onClose, onMade }: { open: boolean; onClose: () => void; onMade: (t: NewToken) => void }) {
  const { token: me, agentId: ownAgent, isAdmin } = useAuth()
  const [name, setName] = useState('')
  const [role, setRole] = useState<Role>('regular')
  const [picked, setPicked] = useState<number | undefined>(undefined)
  const agentId = picked ?? ownAgent
  const allowed = ROLES.filter((r) => me && rankOf(r) <= MAY_HAND_OUT[me.role])
  const options: Option[] = allowed.map((r) => ({ value: r, label: r, icon: ROLE_ICON[r], description: ROLE_HELP[r] }))

  const save = useAction(() => api.createToken({ name: name.trim(), role, agent_id: agentId }), {
    invalidate: ['tokens'],
    onSuccess: (t) => {
      setName('')
      setRole('regular')
      setPicked(undefined)
      onMade(t)
    },
  })

  return (
    <FormDialog
      open={open}
      onClose={onClose}
      title="New token"
      description="A token gives access to one agent, as a role."
      submitLabel="Create"
      onSubmit={() => save.mutate(undefined)}
      submitDisabled={!name.trim() || agentId === undefined}
      pending={save.isPending}
    >
      <FieldGroup>
        <FormField label="Name">
          <Input autoFocus maxLength={NAME_MAX} value={name} onChange={(e) => setName(e.target.value)} placeholder="Telegram bot" />
        </FormField>
        <FormField label="Role">
          <OptionSelect value={role} onChange={(v) => setRole(v as Role)} options={options} />
        </FormField>
        {isAdmin ? <AgentField label="Agent" agentId={agentId} onChange={(v) => setPicked(Number(v))} /> : <AgentField label="Agent" agentId={agentId} onChange={() => undefined} />}
      </FieldGroup>
    </FormDialog>
  )
}

function EditDialog({ token, onClose }: { token: Token | null; onClose: () => void }) {
  const { token: me } = useAuth()
  const [name, setName] = useState<string | null>(null)
  const [role, setRole] = useState<Role | null>(null)
  const shown = name ?? token?.name ?? ''
  const shownRole = role ?? token?.role ?? 'regular'
  // the service refuses the role of the token in use and of the initial one; the panel does not offer it
  const roleFixed = !!token && (token.id === me?.id || token.is_initial)
  const allowed = ROLES.filter((r) => me && rankOf(r) <= MAY_HAND_OUT[me.role])
  const options: Option[] = allowed.map((r) => ({ value: r, label: r, icon: ROLE_ICON[r], description: ROLE_HELP[r] }))
  const reset = () => { setName(null); setRole(null) }
  const changes = { ...(shown.trim() !== token?.name ? { name: shown.trim() } : {}), ...(shownRole !== token?.role ? { role: shownRole } : {}) }
  const save = useAction(() => api.updateToken(token!.id, changes), {
    invalidate: ['tokens'],
    success: 'Token updated',
    onSuccess: () => { reset(); onClose() },
  })
  return (
    <FormDialog
      open={token !== null}
      onClose={() => { reset(); onClose() }}
      title={`Token “${token?.name ?? ''}”`}
      description="The name and the role can change; the agent is fixed: make a new token for another agent. The secret stays the same."
      size="sm"
      submitLabel="Save"
      onSubmit={() => save.mutate(undefined)}
      submitDisabled={!shown.trim() || Object.keys(changes).length === 0}
      pending={save.isPending}
    >
      <FieldGroup>
        <FormField label="Name">
          <Input autoFocus maxLength={NAME_MAX} value={shown} onChange={(e) => setName(e.target.value)} />
        </FormField>
        <FormField
          label="Role"
          description={roleFixed ? (token?.is_initial ? 'The initial token stays an owner.' : 'A token cannot change its own role.') : undefined}
        >
          <OptionSelect value={shownRole} onChange={(v) => setRole(v as Role)} options={options} disabled={roleFixed} />
        </FormField>
      </FieldGroup>
    </FormDialog>
  )
}

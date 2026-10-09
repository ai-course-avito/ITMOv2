import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { BrainIcon, ClockIcon, EraserIcon, BotIcon, ListIcon, MessagesSquareIcon, PencilIcon, PlusIcon, SearchIcon, Trash2Icon, UserRoundIcon, UsersIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Item, ItemActions, ItemContent, ItemDescription, ItemMedia, ItemTitle } from '@/components/ui/item'
import { actionsColumn, DataTable, rowAction, SortHeader } from '@/components/data-table'
import { ConfirmDialog, FormDialog } from '@/components/dialogs'
import { CopyButton } from '@/components/display'
import { AttrChip, FormField } from '@/components/form'
import { AgentField, useActingAgent } from '@/components/agent-field'
import { UserSuggest } from '@/components/user-suggest'
import { MessageBubble } from '@/components/message-bubble'
import { EmptyState, ErrorBox, LoadingRows, Page, PageHeader, QueryBar } from '@/components/page'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useAgents, useSelfAgent } from '@/lib/data'
import { fmtDate } from '@/lib/format'
import { t } from '@/lib/i18n'
import { useAction } from '@/lib/queries'
import { ChatPanel } from '@/components/chat-panel'
import { useChatHistory, useChats } from '@/lib/chats'
import { useRecentUsers } from '@/lib/recent-users'
import type { RecentUser, User } from '@/lib/types'

function NameDialog({ actAs, mode, user, onClose, onDone }: { actAs?: number; mode: 'create' | 'rename' | null; user?: User; onClose: () => void; onDone: (id: string) => void }) {
  const [value, setValue] = useState('')
  useEffect(() => setValue(mode === 'rename' ? (user?.external_id ?? '') : ''), [mode, user])
  const save = useAction(() => (mode === 'create' ? api.createUser(value.trim(), actAs) : api.updateUser(user!.external_id, value.trim(), actAs)), {
    invalidate: ['user', 'history', 'recent-users'],
    success: mode === 'create' ? t('User created') : t('User renamed'),
    onSuccess: (u) => {
      onDone(u.external_id)
      onClose()
    },
  })
  return (
    <FormDialog
      open={mode !== null}
      onClose={onClose}
      title={mode === 'create' ? t('New user') : t('Rename user')}
      description={t('The external id (up to 64 characters) is how your client refers to the user. It must be unique within the agent.')}
      size="sm"
      onSubmit={() => save.mutate(undefined)}
      submitDisabled={!value.trim()}
      pending={save.isPending}
    >
      <FormField label={t('External id')}>
        <Input autoFocus maxLength={64} value={value} onChange={(e) => setValue(e.target.value)} />
      </FormField>
    </FormDialog>
  )
}

export default function UsersPage() {
  const [params, setParams] = useSearchParams()
  const id = params.get('user') ?? ''
  const [input, setInput] = useState(id)
  const { isAdmin, role } = useAuth()
  const { agentId, actAs, own, choose } = useActingAgent()
  const agentKey = agentId ?? 0 // ids differ from agent to agent, so what is remembered is kept per agent
  const recent = useRecentUsers(agentId, actAs)
  const agents = useAgents()
  const selfAgent = useSelfAgent(actAs)
  const agent = agents.data?.find((a) => a.id === agentId) ?? selfAgent.data
  const [dialog, setDialog] = useState<'create' | 'rename' | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [clearing, setClearing] = useState(false)
  useEffect(() => setInput(id), [id])

  const open = (uid: string) =>
    setParams((p) => {
      const n = new URLSearchParams(p)
      if (uid) n.set('user', uid)
      else n.delete('user')
      return n
    })
  const user = useQuery({ queryKey: ['user', agentKey, id], queryFn: () => api.getUser(id, actAs), enabled: id !== '' && agentId !== undefined, retry: false })
  // the chats of the user: one is open (?chat=ID); without one the latest is shown
  const chats = useChats(agentKey, user.data ? id : '', actAs)
  const chatParam = Number(params.get('chat')) || null
  const chatId = chats.data?.some((c) => c.id === chatParam) ? chatParam : (chats.data?.[0]?.id ?? null)
  const chat = chats.data?.find((c) => c.id === chatId)
  const history = useChatHistory(agentKey, user.data ? id : '', chatId, actAs)
  const selectChat = (cid: number | null) =>
    setParams((p) => {
      const n = new URLSearchParams(p)
      if (cid) n.set('chat', String(cid))
      else n.delete('chat')
      return n
    })
  const newChat = useAction(() => api.createChat(id, undefined, actAs), { invalidate: ['chats'], success: t('Chat started'), onSuccess: (c) => selectChat(c.id) })
  const del = useAction((uid: string) => api.deleteUser(uid, actAs), {
    invalidate: ['user', 'chats', 'chat-history', 'recent-users'],
    success: t('User deleted'),
    onSuccess: (u) => {
      setDeleting(null)
      if (u.external_id === id) open('')
    },
  })
  const clear = useAction(() => api.clearChatHistory(id, chatId!, actAs), { invalidate: ['chat-history', 'chats', 'recent-users'], success: t('Chat cleared'), onSuccess: () => setClearing(false) })

  const knownColumns: ColumnDef<RecentUser>[] = [
    {
      accessorKey: 'external_id',
      meta: { label: t('External id') },
      header: ({ column }) => <SortHeader column={column} title={t('External id')} />,
      cell: ({ getValue }) => <span className="font-medium">{getValue<string>()}</span>,
    },
    {
      accessorKey: 'last_active',
      meta: { label: t('Last message') },
      header: ({ column }) => <SortHeader column={column} title={t('Last message')} />,
      cell: ({ getValue }) => fmtDate(getValue<string>()),
    },
    { accessorKey: 'messages', meta: { label: t('Messages') }, header: ({ column }) => <SortHeader column={column} title={t('Messages')} /> },
    actionsColumn<RecentUser>([
      { label: t('Open'), icon: <UserRoundIcon />, onClick: (u) => open(u.external_id) },
      rowAction.remove((u) => setDeleting(u.external_id)),
    ]),
  ]

  return (
    <Page>
      <PageHeader
        title={t('Users & history')}
        description={
          isAdmin
            ? t('Users belong to an agent, and every agent has its own. The service has no list of all users: below are the ones that wrote lately (their messages are still kept), the rest are found by external id.')
            : t('These are the users of your agent. The service has no list of all users: below are the ones that wrote lately (their messages are still kept), the rest are found by external id.')
        }
        actions={
          <Button disabled={agentId === undefined} onClick={() => setDialog('create')}>
            <PlusIcon /> {t('New user')}
          </Button>
        }
      />
      <QueryBar
        onSubmit={() => open(input.trim())}
        actions={
          <>
            {id && (
              <Button type="button" variant="ghost" onClick={() => open('')}>
                <ListIcon /> {t('Recent users')}
              </Button>
            )}
            <Button type="submit" disabled={!input.trim()}>
              <SearchIcon /> {t('Look up')}
            </Button>
          </>
        }
      >
        <AgentField className="w-72" agentId={agentId} onChange={(v) => choose(v, ['user'])} />
        <FormField label={t('External id')} className="min-w-64 flex-1">
          <UserSuggest value={input} onChange={setInput} actAs={actAs} disabled={agentId === undefined} />
        </FormField>
      </QueryBar>

      {!id ? (
        <DataTable
          columns={knownColumns}
          data={recent.data}
          loading={recent.isLoading}
          error={recent.error}
          onRetry={() => recent.refetch()}
          empty={{ icon: UsersIcon, title: t('Nobody has written lately'), description: t('Users whose messages have expired are not listed; look one up by external id, or create a new one.') }}
          searchPlaceholder={t('Search recent users…')}
          getRowId={(u) => String(u.id)}
          onRowClick={(u) => open(u.external_id)}
        />
      ) : user.isError ? (
        <ErrorBox error={user.error} onRetry={() => user.refetch()} />
      ) : !user.data ? (
        <LoadingRows rows={3} />
      ) : (
        <div className="flex min-h-0 flex-1 flex-col gap-3">
          <Item variant="outline">
            <ItemMedia variant="icon">
              <UserRoundIcon />
            </ItemMedia>
            <ItemContent>
              <ItemTitle>
                {user.data.external_id} <CopyButton text={user.data.external_id} label={t('Copy id')} />
              </ItemTitle>
              <ItemDescription className="flex flex-wrap items-center gap-1.5">
                <AttrChip attr={{ text: t('internal id {id}', { id: user.data.id }), mono: true }} />
                <AttrChip attr={{ text: agent?.name ?? t('Agent {id}', { id: user.data.agent_id }), icon: BotIcon, to: role === 'regular' ? undefined : `/agents/${user.data.agent_id}` }} />
                <AttrChip attr={{ text: t('created {date}', { date: fmtDate(user.data.timestamp) }), icon: ClockIcon }} />
              </ItemDescription>
            </ItemContent>
            <ItemActions>
              {role !== 'regular' && own && (
                <Button variant="outline" size="sm" nativeButton={false} render={<Link to={`/memories?user=${encodeURIComponent(id)}`} />}>
                  <BrainIcon /> {t('Memories')}
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={() => setDialog('rename')}>
                <PencilIcon /> {t('Rename')}
              </Button>
              <Button variant="destructive" size="sm" onClick={() => setDeleting(id)}>
                <Trash2Icon /> {t('Delete')}
              </Button>
            </ItemActions>
          </Item>

          <div className="flex min-h-0 flex-1 flex-col gap-3 md:flex-row">
            <ChatPanel
              agentKey={agentKey}
              userId={id}
              actAs={actAs}
              activeId={chatId}
              onSelect={selectChat}
              onNew={() => newChat.mutate(undefined)}
              newPending={newChat.isPending}
              className="max-h-48 shrink-0 md:max-h-none md:w-72"
            />
            <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
              <div className="flex items-center justify-between gap-2">
                <h2 className="flex min-w-0 items-center gap-2 font-medium">
                  <span className="truncate" data-testid="chat-title">{chat?.title ?? t('History')}</span>
                  {history.data && <Badge variant="secondary">{history.data.length}</Badge>}
                </h2>
                <Button variant="outline" size="sm" disabled={!history.data?.length} onClick={() => setClearing(true)}>
                  <EraserIcon /> {t('Clear chat')}
                </Button>
              </div>
              {chats.isLoading || (chatId !== null && history.isLoading) ? (
                <LoadingRows rows={3} />
              ) : chatId === null ? (
                <EmptyState icon={MessagesSquareIcon} title={t('No chats yet')} description={t('A chat starts with the first message of the user, or with New chat.')} className="flex-1" />
              ) : history.isError ? (
                <ErrorBox error={history.error} onRetry={() => history.refetch()} />
              ) : !history.data?.length ? (
                <EmptyState icon={MessagesSquareIcon} title={t('No messages')} description={t('Messages older than the retention period are dropped automatically.')} className="flex-1" />
              ) : (
                <div className="grid min-h-0 flex-1 content-start gap-3 overflow-auto rounded-xl border bg-card p-4">
                  {history.data.map((m) => (
                    <MessageBubble key={m.id} message={m} />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <NameDialog actAs={actAs} mode={dialog} user={user.data} onClose={() => setDialog(null)} onDone={open} />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={t('Delete user {id}?', { id: deleting ?? '' })}
        description={t('The user is removed with their chats, history and memories.')}
        pending={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting)}
      />
      <ConfirmDialog
        open={clearing}
        onOpenChange={setClearing}
        title={t('Clear “{title}”?', { title: chat?.title ?? t('this chat') })}
        description={t('The messages of this chat are deleted; the chat and the other chats stay. Memories stay.')}
        confirmLabel={t('Clear')}
        pending={del.isPending || clear.isPending}
        onConfirm={() => clear.mutate(undefined)}
      />
    </Page>
  )
}

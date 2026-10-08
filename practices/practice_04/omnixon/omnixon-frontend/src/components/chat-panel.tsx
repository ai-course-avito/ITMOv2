import { useState } from 'react'
import { EllipsisVerticalIcon, EraserIcon, MessageSquareIcon, PencilIcon, PlusIcon, Trash2Icon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ConfirmDialog, FormDialog } from '@/components/dialogs'
import { FormField } from '@/components/form'
import { api } from '@/lib/api'
import { useChats } from '@/lib/chats'
import { fmtDate } from '@/lib/format'
import { useAction } from '@/lib/queries'
import { NAME_MAX, type Chat } from '@/lib/types'
import { cn } from '@/lib/utils'

/**
 * The chats of one user: the list, and what can be done with a chat (rename, clear, delete). The Playground and the Users page both
 * show it. Which chat is open is the parent's business (`activeId`, `onSelect`), and so is what "new chat" does.
 */
export function ChatPanel({
  agentKey,
  userId,
  actAs,
  activeId,
  onSelect,
  onNew,
  onCleared,
  newPending,
  disabled,
  className,
}: {
  agentKey: number
  userId: string
  actAs?: number
  activeId: number | null
  onSelect: (chatId: number | null) => void
  onNew: () => void
  /** The messages of a chat were deleted (it stays): whoever shows them should stop. */
  onCleared?: (chatId: number) => void
  newPending?: boolean
  /** An answer is coming: another chat cannot be opened until it is here. */
  disabled?: boolean
  className?: string
}) {
  const chats = useChats(agentKey, userId, actAs)
  const [renaming, setRenaming] = useState<Chat | null>(null)
  const [title, setTitle] = useState('')
  const [clearing, setClearing] = useState<Chat | null>(null)
  const [deleting, setDeleting] = useState<Chat | null>(null)

  const refresh = ['chats', 'chat-history', 'recent-users']
  const rename = useAction((c: Chat) => api.renameChat(userId, c.id, title.trim(), actAs), { invalidate: refresh, success: 'Chat renamed', onSuccess: () => setRenaming(null) })
  const clear = useAction(
    async (c: Chat) => {
      await api.clearChatHistory(userId, c.id, actAs)
      return c
    },
    { invalidate: refresh, success: 'Chat cleared', onSuccess: (c) => { setClearing(null); onCleared?.(c.id) } },
  )
  const del = useAction((c: Chat) => api.deleteChat(userId, c.id, actAs), {
    invalidate: refresh,
    success: 'Chat deleted',
    onSuccess: (c) => {
      setDeleting(null)
      if (c.id === activeId) onSelect(null)
    },
  })

  return (
    <section aria-label="Chats" className={cn('flex min-h-0 flex-col gap-2', className)}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium">
          Chats {chats.data && chats.data.length > 0 && <span className="font-normal text-muted-foreground">({chats.data.length})</span>}
        </h2>
        <Button size="sm" variant="outline" onClick={onNew} disabled={newPending || disabled}>
          <PlusIcon /> New chat
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        {chats.isLoading ? (
          <div className="grid gap-2">
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        ) : chats.isError ? (
          <p className="text-sm text-destructive">Could not read the chats.</p>
        ) : !chats.data?.length ? (
          <p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">{userId ? 'No chats yet: the first message starts one.' : 'The first message starts a chat.'}</p>
        ) : (
          <ul className="grid gap-1">
            {chats.data.map((c) => (
              <li key={c.id} data-testid="chat-item" data-chat-id={c.id} data-active={c.id === activeId ? '' : undefined} className="group relative">
                <button
                  type="button"
                  data-testid="chat-open"
                  disabled={disabled}
                  onClick={() => onSelect(c.id)}
                  aria-current={c.id === activeId ? 'true' : undefined}
                  className={cn(
                    'flex w-full flex-col gap-0.5 rounded-lg px-3 py-2 pr-9 text-left transition-colors hover:bg-muted/60',
                    c.id === activeId && 'bg-muted',
                  )}
                >
                  <span className="flex items-center gap-1.5">
                    <MessageSquareIcon className="size-3.5 shrink-0 text-muted-foreground" />
                    <span className="truncate text-sm font-medium">{c.title}</span>
                    {c.is_default && <Badge variant="outline" className="ml-auto shrink-0">default</Badge>}
                  </span>
                  <span className="flex flex-wrap gap-x-2 text-xs text-muted-foreground">
                    <span>
                      {c.messages} {c.messages === 1 ? 'message' : 'messages'}
                    </span>
                    <span>{fmtDate(c.updated_at)}</span>
                  </span>
                </button>
                <DropdownMenu>
                  <DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" aria-label={`Actions for ${c.title}`} className="absolute top-1.5 right-1" />}>
                    <EllipsisVerticalIcon />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="min-w-40">
                    <DropdownMenuItem
                      onClick={() => {
                        setTitle(c.title)
                        setRenaming(c)
                      }}
                    >
                      <PencilIcon /> Rename
                    </DropdownMenuItem>
                    <DropdownMenuItem disabled={c.messages === 0} onClick={() => setClearing(c)}>
                      <EraserIcon /> Clear messages
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem variant="destructive" onClick={() => setDeleting(c)}>
                      <Trash2Icon /> Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </li>
            ))}
          </ul>
        )}
      </div>

      <FormDialog
        open={renaming !== null}
        onClose={() => setRenaming(null)}
        title="Rename chat"
        size="sm"
        submitLabel="Save"
        onSubmit={() => renaming && rename.mutate(renaming)}
        submitDisabled={!title.trim() || title.trim() === renaming?.title}
        pending={rename.isPending}
      >
        <FormField label="Name">
          <Input autoFocus maxLength={NAME_MAX} value={title} onChange={(e) => setTitle(e.target.value)} />
        </FormField>
      </FormDialog>
      <ConfirmDialog
        open={clearing !== null}
        onOpenChange={(o) => !o && setClearing(null)}
        title={`Clear “${clearing?.title ?? ''}”?`}
        description="Its messages are deleted; the chat stays. Memories stay."
        confirmLabel="Clear"
        pending={clear.isPending}
        onConfirm={() => clearing && clear.mutate(clearing)}
      />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete “${deleting?.title ?? ''}”?`}
        description="The chat is deleted with its messages. Memories stay."
        pending={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting)}
      />
    </section>
  )
}

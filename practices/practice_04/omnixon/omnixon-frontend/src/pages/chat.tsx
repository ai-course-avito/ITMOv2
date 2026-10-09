import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { EraserIcon, FileUpIcon, Link2Icon, MessageSquareIcon, PaperclipIcon, SendIcon, SlidersHorizontalIcon, SquareIcon, XIcon } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { FieldGroup, FieldSeparator } from '@/components/ui/field'
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput, InputGroupTextarea } from '@/components/ui/input-group'
import { Kbd } from '@/components/ui/kbd'
import { Spinner } from '@/components/ui/spinner'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { CopyButton } from '@/components/display'
import { Markdown } from '@/components/markdown'
import ShinyText from '@/components/ShinyText'
import { AgentField, useActingAgent } from '@/components/agent-field'
import { FormField, SwitchField } from '@/components/form'
import { VoiceRecorder } from '@/components/voice-recorder'
import { UserSuggest } from '@/components/user-suggest'
import { EmptyState, Page, PageHeader } from '@/components/page'
import { TraceView } from '@/components/trace-view'
import { ChatPanel } from '@/components/chat-panel'
import { ConfirmDialog, FormDialog } from '@/components/dialogs'
import { api, ApiError, fileToAttachment, streamMessage } from '@/lib/api'
import { newUserId, turnsOf, useChatHistory, useChats } from '@/lib/chats'
import { useSelfAgent } from '@/lib/data'
import { t } from '@/lib/i18n'
import { loadPlayground, savePlayground } from '@/lib/playground-store'
import { errorMessage } from '@/lib/queries'
import type { Attachment, TraceStep } from '@/lib/types'
import { cn } from '@/lib/utils'

interface Turn {
  role: 'user' | 'assistant' | 'error'
  text: string
  files?: string[]
  pending?: boolean
  /** The answer was cut off: this is what had been said. */
  interrupted?: boolean
  /** The chain of calls behind the answer, filling in while it runs. */
  steps?: TraceStep[]
}

const label = (a: Attachment) => a.name ?? a.url ?? a.media_type ?? 'file'

export default function Chat() {
  // you talk as the agent of your token; an admin may pick another agent (its users, its answers: X-Act-As-Agent)
  const { agentId, actAs, choose } = useActingAgent()
  const queryClient = useQueryClient()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const selfAgent = useSelfAgent(actAs)
  const agentKey = agentId ?? 0
  // who the Playground talks as and in which chat: remembered per agent (lib/playground-store.ts), so a reload continues the conversation
  const [userId, setUserId] = useState('')
  const [chatId, setChatId] = useState<number | null>(null)
  const [blank, setBlank] = useState(false) // "New chat" was pressed: an empty page, not the latest chat
  const [userDraft, setUserDraft] = useState('') // what is typed in the settings; it is the user once the dialog is closed
  const [text, setText] = useState('')
  const [stream, setStream] = useState(true)
  const [saveMessage, setSaveMessage] = useState(true)
  const [useMemo, setUseMemo] = useState(true)
  const [trace, setTrace] = useState(true)
  const [files, setFiles] = useState<Attachment[]>([])
  const [urlInput, setUrlInput] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)
  const [clearing, setClearing] = useState(false)
  const abort = useRef<AbortController | null>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const restoredFor = useRef<number | null>(null) // the agent whose remembered state is in place
  const shownKey = useRef<string | null>(null) // the chat whose saved messages are on the screen

  const chats = useChats(agentKey, userId, actAs)
  const history = useChatHistory(agentKey, userId, chatId, actAs)

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end' })
  }, [turns])
  useEffect(() => {
    return () => abort.current?.abort()
  }, [])

  // the remembered user and chat of the agent come back when the page opens (and when another agent is chosen)
  useEffect(() => {
    if (agentId === undefined || restoredFor.current === agentId) return
    restoredFor.current = agentId
    const saved = loadPlayground(agentId)
    setUserId(saved.userId)
    setUserDraft(saved.userId)
    setChatId(saved.chatId)
    setBlank(false)
    setTurns([])
    shownKey.current = null
  }, [agentId])
  useEffect(() => {
    if (agentId !== undefined && restoredFor.current === agentId) savePlayground(agentId, { userId, chatId })
  }, [agentId, userId, chatId])

  // which chat is open: the remembered one if it is still there, else the latest, unless a blank page was asked for
  useEffect(() => {
    if (!chats.data || chats.isFetching || busy) return
    if (chatId !== null && !chats.data.some((c) => c.id === chatId)) setChatId(blank ? null : (chats.data[0]?.id ?? null))
    else if (chatId === null && !blank && chats.data.length) setChatId(chats.data[0].id)
  }, [chats.data, chats.isFetching, chatId, blank, busy])

  // the past of the open chat is shown once, when it has been read (a refetch must not wipe what is on the screen)
  useEffect(() => {
    if (chatId === null || userId === '' || busy) return
    const key = `${agentKey}/${userId}/${chatId}`
    if (shownKey.current === key || !history.data || history.isFetching) return
    shownKey.current = key
    setTurns(turnsOf(history.data).map((turn) => ({ ...turn })))
  }, [history.data, history.isFetching, chatId, userId, agentKey, busy])

  function selectChat(id: number | null) {
    if (busy) return
    setBlank(false) // ("New chat" asks for a blank page itself); null here means the open chat is gone: the latest one is opened
    setChatId(id)
    setTurns([])
    shownKey.current = null
  }

  function switchUser(id: string) {
    if (busy || id === userId) return
    setUserId(id)
    setChatId(null)
    setBlank(false)
    setTurns([])
    shownKey.current = null
  }

  const ready = agentId !== undefined

  const patchLast = (patch: Partial<Turn>) => setTurns((list) => list.map((x, i) => (i === list.length - 1 ? { ...x, ...patch } : x)))

  async function send(e?: FormEvent, withFile?: Attachment) {
    e?.preventDefault()
    const attachments = withFile ? [...files, withFile] : files
    if ((!text.trim() && !attachments.length) || busy || !ready) return
    setTurns((list) => [...list, { role: 'user', text, files: attachments.map(label) }, { role: 'assistant', text: '', pending: true, steps: [] }])
    setText('')
    setFiles([])
    setBusy(true)
    const controller = new AbortController()
    abort.current = controller

    try {
      // the user and the chat are made here when there are none yet, so that what follows is theirs and is remembered
      let uid = userId.trim()
      if (!uid) {
        uid = newUserId()
        await api.createUser(uid, actAs)
        setUserId(uid)
        setUserDraft(uid)
      } else if (chatId === null) {
        try {
          await api.getUser(uid, actAs)
        } catch (e) {
          if (!(e instanceof ApiError && e.status === 404)) throw e
          await api.createUser(uid, actAs) // an id that is not there yet is a new user
        }
      }
      let cid = chatId
      if (cid === null) {
        cid = (await api.createChat(uid, undefined, actAs)).id
        shownKey.current = `${agentKey}/${uid}/${cid}` // what is on the screen is this chat's already
        setChatId(cid)
        setBlank(false)
      }
      const body = { user_id: uid, chat_id: cid, request: text, save_message: saveMessage, use_memo: useMemo, attachments, trace }
      if (stream) {
        let acc = ''
        await streamMessage(
          body,
          {
            onChunk: (c) => {
              acc += c
              patchLast({ text: acc })
            },
            onTrace: (step) => setTurns((list) => list.map((x, i) => (i === list.length - 1 ? { ...x, steps: [...(x.steps ?? []), step] } : x))),
            onInterrupted: () => patchLast({ interrupted: true, pending: false }),
            onError: (detail) => patchLast({ role: 'error', text: detail, pending: false }),
          },
          actAs,
          controller.signal,
        )
        setTurns((list) => list.map((x, i) => (i === list.length - 1 && x.pending ? { ...x, pending: false } : x)))
      } else {
        const res = await api.sendMessage(body, actAs, controller.signal)
        patchLast({ text: res.response, pending: false, steps: res.trace ?? [] })
      }
    } catch (err) {
      if ((err as Error).name === 'AbortError') patchLast({ pending: false })
      else patchLast({ role: 'error', text: errorMessage(err), pending: false })
    } finally {
      setBusy(false)
      abort.current = null
      queryClient.invalidateQueries({ queryKey: ['recent-users'] }) // the user has written: the list of recent users has them now
      queryClient.invalidateQueries({ queryKey: ['chats'] }) // the chat has a title and a new latest message
      queryClient.invalidateQueries({ queryKey: ['chat-history'] }) // and more messages: what was read of it earlier is old
    }
  }

  /** Stop: ask the service to cut the stream (what was said is kept in the history and memory), else just drop the connection. */
  async function stop() {
    if (stream && userId.trim()) {
      try {
        const res = await api.interruptUser(userId.trim(), actAs)
        if (res.interrupted) return // the stream ends by itself with `event: interrupted`
      } catch {
        // fall through to closing the connection
      }
    }
    abort.current?.abort()
  }

  async function pickFiles(list: FileList | null) {
    if (!list) return
    try {
      const added = await Promise.all(Array.from(list).map(fileToAttachment))
      setFiles((f) => [...f, ...added])
    } catch {
      toast.error(t('Could not read the file'))
    }
    if (fileInput.current) fileInput.current.value = ''
  }

  function addUrl() {
    const u = urlInput.trim()
    if (!/^https?:\/\//.test(u)) return toast.error(t('The URL must start with http:// or https://'))
    setFiles((f) => [...f, { url: u }])
    setUrlInput('')
  }

  return (
    <Page>
      <PageHeader
        title={t('Playground')}
        description={t('Talk to an agent through POST /request or /request-stream, with attachments and the per-request flags.')}
        actions={
          <>
            <Button
              size="sm"
              onClick={() => {
                setUserDraft(userId)
                setSettingsOpen(true)
              }}
            >
              <SlidersHorizontalIcon /> {t('Change settings')}
            </Button>
            <Button variant="outline" size="sm" onClick={() => (chatId !== null ? setClearing(true) : setTurns([]))} disabled={busy || !turns.length}>
              <EraserIcon /> {t('Clear chat')}
            </Button>
          </>
        }
      />
      <div className="flex min-h-0 flex-1 flex-col gap-3">
        {/* what the next message will be sent with: the settings are in the dialog, this keeps them in sight */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs" aria-label={t('Current settings')}>
          <Badge variant="outline">{selfAgent.data?.name ?? t('agent')}</Badge>
          <Badge variant="outline" data-testid="chat-user">{userId || t('new user')}</Badge>
          <Badge variant="secondary">{stream ? t('stream') : t('single response')}</Badge>
          <Badge variant="secondary">{useMemo ? t('with history') : t('no history')}</Badge>
          <Badge variant="secondary">{saveMessage ? t('saved') : t('not saved')}</Badge>
          {trace && <Badge variant="secondary">{t('chain of calls')}</Badge>}
        </div>
        <Card className="min-h-0 flex-1 gap-0 py-0 md:flex-row">
          <ChatPanel
            agentKey={agentKey}
            userId={userId}
            actAs={actAs}
            activeId={chatId}
            disabled={busy}
            onSelect={selectChat}
            onCleared={(id) => {
              if (id !== chatId) return
              setTurns([]) // the open chat was emptied: so is the screen
              shownKey.current = null
            }}
            onNew={() => {
              selectChat(null)
              setBlank(true)
            }}
            className="max-h-48 shrink-0 border-b p-3 md:max-h-none md:w-72 md:border-r md:border-b-0"
          />
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 space-y-3 overflow-auto p-4">
            {!turns.length && <EmptyState icon={MessageSquareIcon} title={t('Say something')} description={t('Pick the agent, the user and the options with Change settings.')} className="h-full border-0" />}
            {turns.map((turn, i) => (
              <div key={i} className={cn('flex flex-col gap-1', turn.role === 'user' ? 'items-end' : 'items-start')}>
                {turn.role !== 'user' && (turn.steps?.length || (turn.pending && trace)) ? <TraceView steps={turn.steps ?? []} running={turn.pending} /> : null}
                <div
                  data-testid={turn.role === 'assistant' ? 'answer' : undefined}
                  className={cn(
                    'max-w-[85%] min-w-0 rounded-xl px-3 py-2 text-sm',
                    turn.role !== 'assistant' && 'whitespace-pre-wrap',
                    turn.role === 'user' && 'bg-primary text-primary-foreground',
                    // an answer has no card: no background and no border, it is text on the page of the chat
                    turn.role === 'assistant' && 'bg-transparent px-0 lg:max-w-[min(85%,52rem)]',
                    turn.role === 'error' && 'border border-destructive/40 bg-destructive/10 text-destructive',
                  )}
                >
                  {turn.text ? (
                    turn.role === 'assistant' ? <Markdown>{turn.text}</Markdown> : turn.text
                  ) : turn.pending ? (
                    <ShinyText text={t('Thinking…')} speed={2.5} />
                  ) : (
                    <em className="opacity-60">{t('empty answer')}</em>
                  )}
                  {turn.pending && turn.text && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-current align-middle" />}
                </div>
                {turn.interrupted && (
                  <Badge variant="outline" data-testid="interrupted">
                    <SquareIcon /> {t('interrupted')}
                  </Badge>
                )}
                {turn.role === 'assistant' && turn.text && !turn.pending && <CopyButton text={turn.text} label={t('Copy answer')} />}
                {turn.files?.map((f, j) => (
                  <Badge key={j} variant="secondary">
                    <PaperclipIcon /> {f}
                  </Badge>
                ))}
              </div>
            ))}
            <div ref={bottom} />
          </div>

          <form onSubmit={send} className="grid gap-2 border-t p-3">
            {files.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {files.map((f, i) => (
                  <Badge key={i} variant="secondary" className="h-auto gap-1.5 py-1">
                    <PaperclipIcon /> {label(f)}
                    {f.data && f.media_type?.startsWith('audio/') && <audio controls src={`data:${f.media_type};base64,${f.data}`} className="h-7 max-w-52" aria-label={t('Listen to {name}', { name: label(f) })} />}
                    <button type="button" aria-label={t('Remove')} onClick={() => setFiles((x) => x.filter((_, j) => j !== i))}>
                      <XIcon className="size-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
            <InputGroup className="bg-background shadow-xs has-disabled:bg-background has-disabled:opacity-100 dark:bg-background dark:has-disabled:bg-background">
              <InputGroupTextarea
                rows={3}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) send()
                }}
                placeholder={ready ? t('Message…') : t('Choose an agent first…')}
              />
              <InputGroupAddon align="block-end" className="flex-wrap gap-2">
                <input ref={fileInput} type="file" multiple hidden onChange={(e) => pickFiles(e.target.files)} />
                <InputGroupButton variant="secondary" onClick={() => fileInput.current?.click()}>
                  <FileUpIcon /> {t('File')}
                </InputGroupButton>
                <VoiceRecorder
                  disabled={busy || !ready}
                  onRecorded={(file, sendNow) => {
                    if (sendNow) void send(undefined, file)
                    else setFiles((f) => [...f, file])
                  }}
                />
                <InputGroup className="h-7 w-64">
                  <InputGroupInput
                    aria-label={t('Attachment URL')}
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addUrl()
                      }
                    }}
                    placeholder={t('https://… attachment URL')}
                  />
                  <InputGroupAddon align="inline-end">
                    <InputGroupButton size="icon-xs" aria-label={t('Add URL')} disabled={!urlInput.trim()} onClick={addUrl}>
                      <Link2Icon />
                    </InputGroupButton>
                  </InputGroupAddon>
                </InputGroup>
                <span className="ml-auto hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
                  <Kbd>Ctrl</Kbd>+<Kbd>Enter</Kbd> {t('to send')}
                </span>
                {busy && (
                  <InputGroupButton variant="secondary" onClick={stop}>
                    <SquareIcon /> {t('Stop')}
                  </InputGroupButton>
                )}
                <InputGroupButton type="submit" variant="default" disabled={busy || (!text.trim() && !files.length) || !ready}>
                  {busy ? <Spinner /> : <SendIcon />} {t('Send')}
                </InputGroupButton>
              </InputGroupAddon>
            </InputGroup>
          </form>
          </div>
        </Card>
      </div>
      <ConfirmDialog
        open={clearing}
        onOpenChange={setClearing}
        title={t('Clear this chat?')}
        description={t('Its messages are deleted from the service; the chat stays. Memories stay.')}
        confirmLabel={t('Clear')}
        onConfirm={async () => {
          if (chatId !== null) await api.clearChatHistory(userId, chatId, actAs).catch((e) => toast.error(errorMessage(e)))
          setClearing(false)
          setTurns([])
          queryClient.invalidateQueries({ queryKey: ['chats'] })
          queryClient.invalidateQueries({ queryKey: ['chat-history'] })
          queryClient.invalidateQueries({ queryKey: ['recent-users'] })
        }}
      />
      <FormDialog
        open={settingsOpen}
        onClose={() => {
          setSettingsOpen(false)
          switchUser(userDraft.trim()) // the user typed in the settings is the user now
        }}
        title={t('Playground settings')}
        description={t('Who answers, which user it talks to, and what the next messages are sent with. They apply at once.')}
      >
        <FieldGroup>
          <AgentField
            label={t('Agent')}
            description={t('The agent that answers, and whose users you can pick. Starts on the agent of your token.')}
            agentId={agentId}
            onChange={(v) => {
              choose(v) // ids differ from agent to agent: the user and the chat of that agent come back with it
            }}
          />
          <FormField
            label={t('User id')}
            description={
              <>
                {t('Who the messages are from; their chats are on the left. Any id works: one that does not exist yet is created with the first message. Type 3 characters to find an existing user of this agent. Empty: a new user is made. Applied when this window is closed, and remembered for next time.')}
                {userId && (
                  <>
                    {' '}
                    <Link className="underline underline-offset-4" to={`/users?user=${encodeURIComponent(userId)}`}>
                      {t("Open this user's history")}
                    </Link>
                  </>
                )}
              </>
            }
          >
            <UserSuggest value={userDraft} onChange={setUserDraft} actAs={actAs} disabled={!ready} placeholder={t('new user')} />
          </FormField>
          <FieldSeparator />
          <FormField label={t('Answer')}>
            <ToggleGroup variant="outline" value={[stream ? 'stream' : 'single']} onValueChange={(v) => v.length && setStream(v[0] === 'stream')} className="w-full">
              <ToggleGroupItem value="stream" className="flex-1">
                {t('Stream (SSE)')}
              </ToggleGroupItem>
              <ToggleGroupItem value="single" className="flex-1">
                {t('Single response')}
              </ToggleGroupItem>
            </ToggleGroup>
          </FormField>
          <FieldSeparator>{t('Per request')}</FieldSeparator>
          <SwitchField label={t('Save the exchange')} description="save_message" checked={saveMessage} onCheckedChange={setSaveMessage} />
          <SwitchField label={t('Use history')} description={t("use_memo; memory is set by the agent's tools")} checked={useMemo} onCheckedChange={setUseMemo} />
          <FieldSeparator />
          <SwitchField label={t('Chain of calls')} description={t('trace; shows every model call and tool call behind the answer')} checked={trace} onCheckedChange={setTrace} />
        </FieldGroup>
      </FormDialog>
    </Page>
  )
}

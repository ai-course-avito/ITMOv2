import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeftIcon, ChevronRightIcon, ClockIcon, KeyRoundIcon, RotateCcwIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { JsonView } from '@/components/display'
import { AttrChip, FormField, OptionCombobox } from '@/components/form'
import { EmptyState, ErrorBox, LoadingRows } from '@/components/page'
import { api } from '@/lib/api'
import { useTokens } from '@/lib/data'
import { fmtDate, pretty } from '@/lib/format'
import { t } from '@/lib/i18n'
import { versionOption } from '@/lib/options'
import type { AgentVersion } from '@/lib/types'

const show = (v: unknown) => (typeof v === 'string' ? v : pretty(v))
const onOff = (v: boolean | undefined) => (v === undefined ? t('default') : v ? t('on') : t('off'))

export function DiffView({ changes }: { changes: Record<string, { from: unknown; to: unknown }> }) {
  const entries = Object.entries(changes)
  if (!entries.length) return <EmptyState title={t('No differences')} />
  return (
    <div className="grid gap-3">
      {entries.map(([key, change]) => (
        <div key={key} className="overflow-hidden rounded-lg border">
          <div className="border-b bg-muted/40 px-3 py-1.5 font-mono text-xs font-medium">{key}</div>
          <div className="grid gap-px bg-border sm:grid-cols-2">
            <pre className="overflow-auto bg-destructive/10 p-3 text-xs whitespace-pre-wrap">{show(change.from)}</pre>
            <pre className="overflow-auto bg-success/10 p-3 text-xs whitespace-pre-wrap">{show(change.to)}</pre>
          </div>
        </div>
      ))}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{title}</h3>
      {children}
    </div>
  )
}

function Overview({ version }: { version: AgentVersion }) {
  const s = version.snapshot
  const cfg = s.config ?? {}
  const model = (s.model ?? {}) as Record<string, unknown>
  const { model: modelId, ...params } = model
  const servers = (s.mcp_servers ?? []) as Record<string, unknown>[]
  return (
    <div className="grid gap-5">
      <Section title={t('System prompt')}>
        <pre className="max-h-64 overflow-auto rounded-lg border bg-muted/30 p-3 text-sm whitespace-pre-wrap">
          {s.prompt || t('(empty)')}
        </pre>
      </Section>
      <Separator />
      <div className="grid gap-5 sm:grid-cols-2">
        <Section title={t('Model')}>
          <div className="text-sm">
            <span className="font-medium">{String(modelId ?? '?')}</span>{' '}
            <span className="text-muted-foreground">{t('(record {id})', { id: s.model_id })}</span>
          </div>
          {Object.keys(params).length > 0 && <JsonView value={params} className="max-h-40" />}
        </Section>
        <Section title={t('Settings')}>
          <div className="flex flex-wrap gap-1">
            {(cfg.tools ?? []).map((tool) => (
              <Badge key={tool} variant="secondary">
                {tool}
              </Badge>
            ))}
            {!(cfg.tools ?? []).length && <span className="text-sm text-muted-foreground">{t('no tools')}</span>}
          </div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted-foreground">{t('Message limit')}</dt>
            <dd>{cfg.message_limit ?? t('default')}</dd>
            <dt className="text-muted-foreground">{t('Memory limit')}</dt>
            <dd>{cfg.memo_limit ?? t('default')}</dd>
            <dt className="text-muted-foreground">{t('Knowledge limit')}</dt>
            <dd>{cfg.rag_limit ?? t('default')}</dd>
            <dt className="text-muted-foreground">{t('Auto memory')}</dt>
            <dd>{onOff(cfg.auto_memory)}</dd>
            <dt className="text-muted-foreground">{t('Parallel tool calls')}</dt>
            <dd>{onOff(cfg.parallel_tool_calls)}</dd>
          </dl>
        </Section>
      </div>
      <Separator />
      <Section title={t('MCP servers ({count})', { count: servers.length })}>
        {servers.length ? (
          <ul className="grid gap-1 text-sm">
            {servers.map((m, i) => (
              <li key={i} className="value-mono">
                {String(m.url ?? '')}{' '}
                <span className="text-muted-foreground">{String(m.transport ?? 'streamable_http')}</span>
              </li>
            ))}
          </ul>
        ) : (
          <span className="text-sm text-muted-foreground">{t('None attached')}</span>
        )}
      </Section>
    </div>
  )
}

function Changes({ agentId, number, versions }: { agentId: number; number: number; versions: AgentVersion[] }) {
  const latest = versions[0]?.number
  const [to, setTo] = useState<string>('latest')
  useEffect(() => setTo('latest'), [number])
  const target = to === 'latest' ? latest : Number(to)
  const same = target === number
  const q = useQuery({
    queryKey: ['diff', agentId, number, target],
    queryFn: () => api.diff(agentId, number, target),
    enabled: !same && target !== undefined,
  })
  return (
    <div className="grid gap-4">
      <FormField label={t('Compare with')}>
        <OptionCombobox
          value={to}
          onChange={setTo}
          options={versions.map((v) => ({
            ...versionOption(v, latest),
            value: v.number === latest ? 'latest' : String(v.number),
          }))}
        />
      </FormField>
      {same ? (
        <EmptyState title={t('Nothing to compare')} description={t('Pick another version.')} />
      ) : q.isError ? (
        <ErrorBox error={q.error} />
      ) : !q.data ? (
        <LoadingRows rows={3} />
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            {t('Version {from} → {to}. Red is the older value, green the newer.', { from: q.data.from_version, to: q.data.to_version })}
          </p>
          <DiffView changes={q.data.changes} />
        </>
      )}
    </div>
  )
}

/** A past version of an agent: what it was, what changed since, and a button to go back to it. */
export function VersionViewer({
  agentId,
  versions,
  number,
  initialTab = 'overview',
  onNumberChange,
  onClose,
  onRollback,
}: {
  agentId: number
  versions: AgentVersion[]
  number: number | null
  initialTab?: 'overview' | 'changes' | 'json'
  onNumberChange: (n: number) => void
  onClose: () => void
  onRollback: (n: number) => void
}) {
  const tokens = useTokens(agentId)
  const [tab, setTab] = useState<string>(initialTab)
  useEffect(() => setTab(initialTab), [initialTab, number])
  const q = useQuery({
    queryKey: ['version', agentId, number],
    queryFn: () => api.version(agentId, number!),
    enabled: number !== null,
  })
  const latest = versions[0]?.number
  const index = versions.findIndex((v) => v.number === number)
  const older = versions[index + 1]
  const newer = index > 0 ? versions[index - 1] : undefined

  return (
    <Dialog open={number !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {t('Version {number}', { number })} {number === latest && <Badge>{t('current')}</Badge>}
          </DialogTitle>
          <DialogDescription className="flex flex-wrap items-center gap-2">
            {q.data ? (
              <>
                <span>{q.data.comment ?? t('no comment')}</span>
                <AttrChip attr={{ text: fmtDate(q.data.timestamp), icon: ClockIcon }} />
                {q.data.created_by_token_id != null && (
                  <AttrChip
                    attr={{
                      text:
                        tokens.data?.find((tk) => tk.id === q.data.created_by_token_id)?.name ??
                        t('Token {id}', { id: q.data.created_by_token_id }),
                      icon: KeyRoundIcon,
                    }}
                  />
                )}
              </>
            ) : (
              t('Loading…')
            )}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" disabled={!older} onClick={() => older && onNumberChange(older.number)}>
            <ChevronLeftIcon /> {t('Older')}
          </Button>
          <Button variant="outline" size="sm" disabled={!newer} onClick={() => newer && onNumberChange(newer.number)}>
            {t('Newer')} <ChevronRightIcon />
          </Button>
          <div className="ml-auto">
            <Button
              disabled={number === null || number === latest}
              onClick={() => number !== null && onRollback(number)}
            >
              <RotateCcwIcon /> {t('Roll back to this version')}
            </Button>
          </div>
        </div>
        {q.isError ? (
          <ErrorBox error={q.error} />
        ) : !q.data || number === null ? (
          <LoadingRows rows={4} />
        ) : (
          <Tabs value={tab} onValueChange={(v) => v && setTab(String(v))}>
            <TabsList className="mb-3">
              <TabsTrigger value="overview">{t('Overview')}</TabsTrigger>
              <TabsTrigger value="changes">{t('Changes')}</TabsTrigger>
              <TabsTrigger value="json">JSON</TabsTrigger>
            </TabsList>
            <TabsContent value="overview">
              <Overview version={q.data} />
            </TabsContent>
            <TabsContent value="changes">
              <Changes agentId={agentId} number={number} versions={versions} />
            </TabsContent>
            <TabsContent value="json">
              <JsonView value={q.data.snapshot} className="max-h-[55vh]" />
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  )
}

import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { ChevronDownIcon, CpuIcon, PlusIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { FieldGroup, FieldSeparator } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  actionsColumn,
  createdColumn,
  DataTable,
  idColumn,
  nameColumn,
  rowAction,
  SortHeader,
} from '@/components/data-table'
import { ConfirmDialog, FormDialog } from '@/components/dialogs'
import { FormField, JsonEditor, SwitchField } from '@/components/form'
import { LoadingRows, Page, PageHeader } from '@/components/page'
import { api } from '@/lib/api'
import { modelName, useAgents, useModels } from '@/lib/data'
import { clip, parseJsonObject, pretty } from '@/lib/format'
import { t } from '@/lib/i18n'
import { useAction } from '@/lib/queries'
import { useOpenParam } from '@/lib/use-open-param'
import { DEFAULT_BASE_URL, NAME_MAX, type Model, type ModelConnection } from '@/lib/types'

// The sampling keys that get their own input; everything else stays in the JSON box.
const NUMERIC = [
  { key: 'temperature', label: t('Temperature'), hint: '0 – 2' },
  { key: 'top_p', label: 'Top P', hint: '0 – 1' },
  { key: 'max_tokens', label: t('Max tokens'), hint: t('a tiny value on a reasoning model gives an empty answer') },
  { key: 'frequency_penalty', label: t('Frequency penalty'), hint: '' },
  { key: 'presence_penalty', label: t('Presence penalty'), hint: '' },
  { key: 'seed', label: 'Seed', hint: '' },
] as const

interface Draft {
  name: string
  model: string
  numbers: Record<string, string>
  rest: string
  // external model settings (how the model is reached)
  baseUrl: string // empty: OpenRouter
  useProxy: boolean
  apiToken: string // a new key to store; never filled from the service
  clearToken: boolean
}

const emptyDraft: Draft = {
  name: '',
  model: '',
  numbers: {},
  rest: '',
  baseUrl: '',
  useProxy: true,
  apiToken: '',
  clearToken: false,
}

/** The address as the form shows it: empty for OpenRouter's own. */
const shownUrl = (m?: Pick<Model, 'base_url'>) => (!m || m.base_url === DEFAULT_BASE_URL ? '' : m.base_url)

function toDraft(
  name: string,
  json: Record<string, unknown>,
  connection?: Pick<Model, 'base_url' | 'use_proxy'>,
): Draft {
  const numbers: Record<string, string> = {}
  const rest = { ...json }
  delete rest.model
  for (const { key } of NUMERIC) {
    if (typeof rest[key] === 'number') {
      numbers[key] = String(rest[key])
      delete rest[key]
    }
  }
  return {
    ...emptyDraft,
    name,
    model: typeof json.model === 'string' ? json.model : '',
    numbers,
    rest: Object.keys(rest).length ? pretty(rest) : '',
    baseUrl: shownUrl(connection),
    useProxy: connection?.use_proxy ?? true,
  }
}

function fromDraft(d: Draft): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } {
  const rest = parseJsonObject(d.rest)
  if (!rest.ok) return { ok: false, error: t('Other options: {error}', { error: rest.error }) }
  const value: Record<string, unknown> = { model: d.model.trim() }
  for (const { key, label } of NUMERIC) {
    const raw = d.numbers[key]?.trim()
    if (!raw) continue
    if (Number.isNaN(Number(raw))) return { ok: false, error: t('{label} must be a number', { label }) }
    value[key] = Number(raw)
  }
  return { ok: true, value: { ...value, ...rest.value } }
}

type Editing = Model | { copyOf: Model } | 'new' | null

function ModelDialog({ editing, onClose }: { editing: Editing; onClose: () => void }) {
  const open = editing !== null
  const id = editing && editing !== 'new' && 'id' in editing ? editing.id : null
  // Fetch the record fresh (GET /models/{id}) so an edit starts from what is stored
  const fresh = useQuery({ queryKey: ['model', id], queryFn: () => api.model(id!), enabled: open && id !== null })
  const [draft, setDraft] = useState<Draft>(emptyDraft)
  // The form starts from the record once per opening. A refetch of the record (a window focus, a stale copy being
  // replaced) must not wipe what is being typed, so it is not an input of the form after that.
  const started = useRef(false)
  useEffect(() => {
    if (!open) {
      started.current = false
      return
    }
    if (started.current) return
    if (editing === 'new') setDraft(emptyDraft)
    else if (editing && 'copyOf' in editing)
      setDraft(toDraft(`${editing.copyOf.name} (copy)`.slice(0, NAME_MAX), editing.copyOf.request_json, editing.copyOf))
    else if (fresh.data && !fresh.isFetching) setDraft(toDraft(fresh.data.name, fresh.data.request_json, fresh.data))
    else return // the record is not here yet (or a stale copy is being replaced)
    started.current = true
  }, [open, editing, fresh.data, fresh.isFetching])

  const built = fromDraft(draft)
  // what is sent of the connection: on create what is filled in; on update only what changed
  const connection = (): ModelConnection => {
    const base_url = draft.baseUrl.trim()
    const token = draft.apiToken.trim()
    if (id === null)
      return { ...(base_url ? { base_url } : {}), use_proxy: draft.useProxy, ...(token ? { api_token: token } : {}) }
    return {
      ...(base_url !== shownUrl(fresh.data) ? { base_url } : {}),
      ...(draft.useProxy !== fresh.data?.use_proxy ? { use_proxy: draft.useProxy } : {}),
      ...(token ? { api_token: token } : draft.clearToken ? { api_token: '' } : {}),
    }
  }
  const save = useAction(
    (body: Record<string, unknown>) =>
      id === null
        ? api.createModel(draft.name.trim(), body, connection())
        : api.updateModel(id, {
            request_json: body,
            ...(draft.name.trim() !== fresh.data?.name ? { name: draft.name.trim() } : {}),
            ...connection(),
          }),
    {
      invalidate: ['models', 'model', 'agents', 'versions'],
      success: id === null ? t('Model created') : t('Model updated'),
      onSuccess: onClose,
    },
  )
  const setNum = (key: string, v: string) => setDraft((d) => ({ ...d, numbers: { ...d.numbers, [key]: v } }))

  return (
    <FormDialog
      open={open}
      onClose={onClose}
      title={id === null ? t('New model') : t('Model “{name}”', { name: fresh.data?.name ?? String(id) })}
      description={
        <>
          {t('An OpenRouter request body. Sampling keys are applied as settings;')} <code>provider</code>,{' '}
          <code>reasoning</code>, <code>transforms</code>… {t('go to OpenRouter; anything else is sent as')}{' '}
          <code>extra_body</code>.
        </>
      }
      size="lg"
      onSubmit={() => built.ok && save.mutate(built.value)}
      submitDisabled={!built.ok || draft.model.trim() === '' || draft.name.trim() === ''}
      pending={save.isPending}
      problem={built.ok ? undefined : built.error}
    >
      {id !== null && fresh.isLoading ? (
        <LoadingRows rows={3} />
      ) : (
        <FieldGroup>
          <FormField label={t('Name')}>
            <Input
              maxLength={NAME_MAX}
              value={draft.name}
              onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
              placeholder={t('Fast and cheap')}
            />
          </FormField>
          <FormField label={t('Model')}>
            <Input
              value={draft.model}
              onChange={(e) => setDraft((d) => ({ ...d, model: e.target.value }))}
              placeholder="openai/gpt-4o-mini"
            />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-3">
            {NUMERIC.map((n) => (
              <FormField key={n.key} label={n.label} description={n.hint || undefined}>
                <Input
                  inputMode="decimal"
                  value={draft.numbers[n.key] ?? ''}
                  onChange={(e) => setNum(n.key, e.target.value)}
                  placeholder={t('default')}
                />
              </FormField>
            ))}
          </div>
          <FieldSeparator />
          <FormField
            label={t('Other options (JSON)')}
            description={t('stop, logit_bias, parallel_tool_calls, provider, reasoning, transforms, anything for extra_body…')}
          >
            <JsonEditor
              value={draft.rest}
              onChange={(v) => setDraft((d) => ({ ...d, rest: v }))}
              rows={6}
              placeholder={'{\n  "reasoning": {"effort": "low"}\n}'}
            />
          </FormField>
          <Collapsible className="rounded-lg border">
            <CollapsibleTrigger className="group flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm font-medium">
              {t('External model settings')}
              <ChevronDownIcon className="size-4 text-muted-foreground transition-transform group-data-panel-open:rotate-180" />
            </CollapsibleTrigger>
            <CollapsibleContent>
              <FieldGroup className="border-t p-3">
                <FormField
                  label={t('Base URL')}
                  description={t('Another OpenAI-compatible server (a local vLLM or Ollama, another provider). Empty: OpenRouter, {url}.', { url: DEFAULT_BASE_URL })}
                >
                  <Input
                    value={draft.baseUrl}
                    onChange={(e) => setDraft((d) => ({ ...d, baseUrl: e.target.value }))}
                    placeholder={DEFAULT_BASE_URL}
                  />
                </FormField>
                <SwitchField
                  label={t('Use proxy')}
                  description={t('Reach the model through the proxy of the service. Off: it is called directly.')}
                  checked={draft.useProxy}
                  onCheckedChange={(v) => setDraft((d) => ({ ...d, useProxy: v }))}
                />
                <FormField
                  label={t('API token')}
                  description={
                    id !== null && fresh.data?.has_api_token
                      ? draft.clearToken
                        ? t('The key of this model will be removed: the key of the service is used again.')
                        : t('This model has a key of its own (it is never shown). Type a new one to replace it.')
                      : t('The key for this server. Empty: the key of the service is used. Never shown again.')
                  }
                >
                  <Input
                    type="password"
                    autoComplete="off"
                    value={draft.apiToken}
                    onChange={(e) => setDraft((d) => ({ ...d, apiToken: e.target.value, clearToken: false }))}
                    placeholder={
                      id !== null && fresh.data?.has_api_token && !draft.clearToken
                        ? t('•••••••• (set)')
                        : t('the key of the service')
                    }
                  />
                </FormField>
                {id !== null && fresh.data?.has_api_token && !draft.clearToken && !draft.apiToken && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="self-start"
                    onClick={() => setDraft((d) => ({ ...d, clearToken: true }))}
                  >
                    {t('Remove the key of this model')}
                  </Button>
                )}
                {editing && typeof editing === 'object' && 'copyOf' in editing && editing.copyOf.has_api_token && (
                  <p className="text-xs text-muted-foreground">{t('The key of the original is not copied.')}</p>
                )}
              </FieldGroup>
            </CollapsibleContent>
          </Collapsible>
          {id !== null && (
            <p className="text-xs text-muted-foreground">
              {t('Saving records a new version of every agent that uses this model.')}
            </p>
          )}
        </FieldGroup>
      )}
    </FormDialog>
  )
}

const hostOf = (url: string) => {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

// derived fields live in the data, not in the column accessors (see agents.tsx)
type Row = Model & { agentCount: number }

export default function Models() {
  const models = useModels()
  const agents = useAgents()
  const [editing, setEditing] = useState<Editing>(null)
  const [deleting, setDeleting] = useState<Model | null>(null)
  const del = useAction((id: number) => api.deleteModel(id), {
    invalidate: ['models'],
    success: t('Model deleted'),
    onSuccess: () => setDeleting(null),
  })
  useOpenParam(models.data, setEditing)
  const rows = useMemo<Row[] | undefined>(
    () => models.data?.map((m) => ({ ...m, agentCount: agents.data?.filter((a) => a.model_id === m.id).length ?? 0 })),
    [models.data, agents.data],
  )

  const columns: ColumnDef<Row>[] = [
    { ...idColumn<Row>(), size: 80 },
    {
      ...nameColumn<Row>(),
      cell: ({ row }) => (
        <span className="flex items-center gap-2">
          <span className="font-medium">{row.original.name}</span>
          {row.original.id === 0 && <Badge variant="secondary">{t('default')}</Badge>}
        </span>
      ),
    },
    {
      id: 'model',
      meta: { label: t('Model') },
      accessorFn: (m) => modelName(m.request_json),
      header: ({ column }) => <SortHeader column={column} title={t('Model')} />,
      cell: ({ row, getValue }) => (
        <span className="flex flex-wrap items-center gap-2">
          <span className="value-mono">{getValue<string>()}</span>
          {row.original.base_url !== DEFAULT_BASE_URL && (
            <Badge variant="outline">{hostOf(row.original.base_url)}</Badge>
          )}
          {!row.original.use_proxy && <Badge variant="outline">{t('no proxy')}</Badge>}
        </span>
      ),
    },
    {
      id: 'settings',
      meta: { label: t('Settings') },
      accessorFn: (m) => {
        const { model: _m, ...rest } = m.request_json
        void _m
        return Object.keys(rest).length ? JSON.stringify(rest) : ''
      },
      header: t('Settings'),
      cell: ({ getValue }) => (
        <span className="value-mono text-muted-foreground" title={getValue<string>() || undefined}>
          {clip(getValue<string>()) || '—'}
        </span>
      ),
    },
    {
      accessorKey: 'agentCount',
      meta: { label: t('Agents') },
      header: ({ column }) => <SortHeader column={column} title={t('Agents')} />,
    },
    createdColumn<Row>(),
    actionsColumn<Row>([
      rowAction.edit((m) => setEditing(m)),
      rowAction.duplicate((m) => setEditing({ copyOf: m })),
      rowAction.remove(
        (m) => setDeleting(m),
        (m) => m.id === 0,
      ),
    ]),
  ]

  return (
    <Page>
      <PageHeader
        title={t('Models')}
        description={t('OpenRouter request bodies that agents run on. Model 0 is the default and cannot be deleted.')}
        actions={
          <Button onClick={() => setEditing('new')}>
            <PlusIcon /> {t('New model')}
          </Button>
        }
      />
      <DataTable
        columns={columns}
        data={rows}
        loading={models.isLoading}
        error={models.error}
        onRetry={() => models.refetch()}
        empty={{ icon: CpuIcon, title: t('No models yet') }}
        searchPlaceholder={t('Search models…')}
        getRowId={(m) => String(m.id)}
        onRowClick={(m) => setEditing(m)}
      />
      <ModelDialog editing={editing} onClose={() => setEditing(null)} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={t('Delete model “{name}”?', { name: deleting?.name ?? '' })}
        description={t('A model that an agent uses cannot be deleted; the service will answer 409.')}
        pending={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting.id)}
      />
    </Page>
  )
}

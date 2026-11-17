import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { BookOpenIcon, PlusIcon, SearchIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FieldGroup, FieldSeparator } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from '@/components/ui/input-group'
import { Textarea } from '@/components/ui/textarea'
import { actionsColumn, createdColumn, DataTable, idColumn, rowAction } from '@/components/data-table'
import { ConfirmDialog, FormDialog } from '@/components/dialogs'
import { CheckboxField, FormField, JsonEditor } from '@/components/form'
import { AgentField } from '@/components/agent-field'
import { ExportButton, ImportButton, ImportDialog } from '@/components/kb-transfer'
import { LoadingRows, Page, PageHeader, QueryBar } from '@/components/page'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useAgents, useCurrentAgentId } from '@/lib/data'
import { parseJsonObject, pretty, truncate } from '@/lib/format'
import { t } from '@/lib/i18n'
import { useAction } from '@/lib/queries'
import type { RAG } from '@/lib/types'

function RagDialog({ agentId, agentName, editing, onClose }: { agentId: number; agentName: string; editing: RAG | 'new' | null; onClose: () => void }) {
  const open = editing !== null
  const id = editing && editing !== 'new' ? editing.id : null
  const fresh = useQuery({ queryKey: ['rag-entry', agentId, id], queryFn: () => api.rag(id!, agentId), enabled: open && id !== null })
  const [content, setContent] = useState('')
  const [embedText, setEmbedText] = useState('')
  const [meta, setMeta] = useState('')

  useEffect(() => {
    if (!open) return
    if (editing === 'new') {
      setContent('')
      setEmbedText('')
      setMeta('')
    } else if (fresh.data) {
      setContent(fresh.data.content ?? '')
      setEmbedText('')
      setMeta(Object.keys(fresh.data.metadata).length ? pretty(fresh.data.metadata) : '')
    }
  }, [open, editing, fresh.data])

  const parsed = parseJsonObject(meta)
  const save = useAction(
    () => {
      const body = { content, embedding_content: embedText.trim() || null, metadata: parsed.ok ? parsed.value : null }
      return id === null ? api.createRag(body, agentId) : api.updateRag(id, body, agentId)
    },
    { invalidate: ['rag', 'rag-entry'], success: id === null ? t('Entry created') : t('Entry updated'), onSuccess: onClose },
  )

  return (
    <FormDialog
      open={open}
      onClose={onClose}
      title={id === null ? t('New knowledge entry') : t('Entry {id}', { id })}
      description={t('For agent {agent}. The text is embedded for semantic search each time it is saved.', { agent: agentName })}
      size="lg"
      onSubmit={() => save.mutate(undefined)}
      submitDisabled={!content.trim() || !parsed.ok}
      pending={save.isPending}
    >
      {id !== null && fresh.isLoading ? (
        <LoadingRows rows={3} />
      ) : (
        <FieldGroup>
          <FormField label={t('Content')}>
            <Textarea rows={8} value={content} onChange={(e) => setContent(e.target.value)} />
          </FormField>
          <FieldSeparator />
          <FormField label={t('Text to embed (optional)')} description={t('Embed this instead of the content, e.g. a title or a question the content answers.')}>
            <Input value={embedText} onChange={(e) => setEmbedText(e.target.value)} />
          </FormField>
          <FormField label={t('Metadata (JSON, optional)')}>
            <JsonEditor value={meta} onChange={setMeta} rows={5} placeholder={'{"source": "faq.md"}'} />
          </FormField>
        </FieldGroup>
      )}
    </FormDialog>
  )
}

export default function Rag() {
  const [params, setParams] = useSearchParams()
  const agents = useAgents()
  const { isAdmin } = useAuth()
  const ownAgentId = useCurrentAgentId()
  const agentId = (isAdmin ? Number(params.get('agent')) : 0) || ownAgentId
  const agent = agents.data?.find((a) => a.id === agentId)
  const [importing, setImporting] = useState(false)
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')
  const [limit, setLimit] = useState('10')
  const [withEmbedding, setWithEmbedding] = useState(false)
  const [lookupId, setLookupId] = useState('')
  const [editing, setEditing] = useState<RAG | 'new' | null>(null)
  const [deleting, setDeleting] = useState<RAG | null>(null)

  // without a query every entry of the agent is shown; with one, the closest by meaning
  const results = useQuery({
    queryKey: ['rag', agentId, submitted, limit, withEmbedding],
    queryFn: () => (submitted === '' ? api.allRag(agentId) : api.searchRag(submitted, agentId, Number(limit) || 10, withEmbedding)),
    enabled: agentId !== undefined,
  })
  const del = useAction((r: RAG) => api.deleteRag(r.id, agentId), { invalidate: ['rag', 'rag-entry'], success: t('Entry deleted'), onSuccess: () => setDeleting(null) })
  const open = useAction(async (id: number) => api.rag(id, agentId), { onSuccess: (r) => setEditing(r) })

  const columns: ColumnDef<RAG>[] = [
    idColumn<RAG>(),
    {
      accessorKey: 'content',
      meta: { label: t('Content') },
      header: t('Content'),
      cell: ({ getValue }) => <span className="block max-w-2xl whitespace-normal">{truncate(getValue<string | null>() ?? '', 300)}</span>,
    },
    {
      id: 'metadata',
      meta: { label: t('Metadata') },
      accessorFn: (r) => (Object.keys(r.metadata).length ? JSON.stringify(r.metadata) : ''),
      header: t('Metadata'),
      cell: ({ row }) => (
        <span className="flex flex-wrap gap-1">
          {Object.entries(row.original.metadata).map(([k, v]) => (
            <Badge key={k} variant="outline">
              {k}: {truncate(typeof v === 'string' ? v : JSON.stringify(v), 30)}
            </Badge>
          ))}
          {row.original.embedding && <Badge variant="secondary">{t('{dim}-dim embedding', { dim: row.original.embedding.length })}</Badge>}
        </span>
      ),
    },
    createdColumn<RAG>(),
    actionsColumn<RAG>([rowAction.edit((r) => setEditing(r)), rowAction.remove((r) => setDeleting(r))]),
  ]

  return (
    <Page>
      <PageHeader
        title={t('Knowledge base')}
        description={t('Per-agent RAG entries. Every entry of the agent is listed; enter a query to find the closest ones by meaning.')}
        actions={
          <>
            <ExportButton agent={agent} />
            <ImportButton disabled={!agent} onClick={() => setImporting(true)} />
            <Button disabled={agentId === undefined} onClick={() => setEditing('new')}>
              <PlusIcon /> {t('New entry')}
            </Button>
          </>
        }
      />
      <QueryBar
        onSubmit={() => setSubmitted(query.trim())}
        actions={
          <Button type="submit" disabled={agentId === undefined || (!query.trim() && submitted === '')}>
            <SearchIcon /> {t('Search')}
          </Button>
        }
      >
        <AgentField className="w-64" agentId={agentId} onChange={(v) => setParams({ agent: v })} />
        <FormField label={t('Search')} className="min-w-64 flex-1">
          <Input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              if (!e.target.value.trim()) setSubmitted('') // an emptied search shows everything again
            }}
            placeholder={t('What is the refund policy?')}
          />
        </FormField>
        <FormField label={t('Search limit')} className="w-28">
          <Input type="number" min={1} max={100} value={limit} disabled={!query.trim()} onChange={(e) => setLimit(e.target.value)} />
        </FormField>
        <FormField label={t('Open by ID')} className="w-40">
          <InputGroup>
            <InputGroupInput type="number" value={lookupId} onChange={(e) => setLookupId(e.target.value)} />
            <InputGroupAddon align="inline-end">
              <InputGroupButton disabled={!lookupId || agentId === undefined || open.isPending} onClick={() => open.mutate(Number(lookupId))}>
                {t('Open')}
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
        </FormField>
        <CheckboxField label={t('With embeddings')} checked={withEmbedding} onCheckedChange={setWithEmbedding} />
      </QueryBar>

      <DataTable
        columns={columns}
        data={results.data}
        loading={results.isLoading || (results.isFetching && !results.data)}
        error={results.error}
        onRetry={() => results.refetch()}
        empty={
          submitted === ''
            ? { icon: BookOpenIcon, title: t('The knowledge base is empty'), description: t('Add an entry, or import a JSON array of strings.') }
            : { icon: BookOpenIcon, title: t('Nothing found') }
        }
        searchPlaceholder={submitted === '' ? t('Filter the entries…') : t('Filter these results…')}
        getRowId={(r) => String(r.id)}
        onRowClick={(r) => setEditing(r)}
      />
      <ImportDialog agent={agent} open={importing} onClose={() => setImporting(false)} />
      {agentId !== undefined && <RagDialog key={editing === 'new' ? 'new' : (editing?.id ?? 'none')} agentId={agentId} agentName={agent?.name ?? t('Agent {id}', { id: agentId })} editing={editing} onClose={() => setEditing(null)} />}
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={t('Delete entry {id}?', { id: deleting?.id ?? '' })}
        pending={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting)}
      />
    </Page>
  )
}

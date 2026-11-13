import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { RefreshCwIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from '@/components/ui/input-group'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { DataTable, SortHeader } from '@/components/data-table'
import { ErrorBox, Page, PageHeader } from '@/components/page'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n'

interface Sample {
  name: string
  labels: string
  value: string
}

// Prometheus text exposition format: `name{label="x"} value`, `# TYPE` / `# HELP` comments
function parse(text: string) {
  const help = new Map<string, string>()
  const samples: Sample[] = []
  for (const line of text.split('\n')) {
    if (!line.trim()) continue
    if (line.startsWith('# HELP ')) {
      const rest = line.slice(7)
      const i = rest.indexOf(' ')
      help.set(rest.slice(0, i), rest.slice(i + 1))
      continue
    }
    if (line.startsWith('#')) continue
    const m = line.match(/^([^{\s]+)(\{.*\})?\s+(\S+)/)
    if (m) samples.push({ name: m[1], labels: m[2]?.slice(1, -1) ?? '', value: m[3] })
  }
  return { help, samples }
}

export default function Metrics() {
  const [auto, setAuto] = useState(true)
  const [prefix, setPrefix] = useState('omnixon_')
  const q = useQuery({ queryKey: ['metrics'], queryFn: api.metrics, refetchInterval: auto ? 5000 : false })
  const parsed = useMemo(() => parse(q.data ?? ''), [q.data])
  const rows = useMemo(() => parsed.samples.filter((s) => s.name.toLowerCase().includes(prefix.toLowerCase())), [parsed, prefix])

  const columns: ColumnDef<Sample>[] = [
    {
      accessorKey: 'name',
      meta: { label: t('Metric') },
      header: ({ column }) => <SortHeader column={column} title={t('Metric')} />,
      cell: ({ row }) => (
        <span className="value-mono" title={parsed.help.get(row.original.name)}>
          {row.original.name}
        </span>
      ),
    },
    {
      accessorKey: 'labels',
      meta: { label: t('Labels') },
      header: t('Labels'),
      cell: ({ getValue }) => <span className="value-mono block max-w-xl truncate text-muted-foreground">{getValue<string>()}</span>,
    },
    {
      accessorKey: 'value',
      meta: { label: t('Value') },
      sortingFn: (a, b) => Number(a.original.value) - Number(b.original.value),
      header: ({ column }) => <SortHeader column={column} title={t('Value')} />,
      cell: ({ getValue }) => <span className="value-mono">{getValue<string>()}</span>,
    },
  ]

  return (
    <Page>
      <PageHeader
        title={t('Metrics')}
        description={t('Prometheus metrics of the service (/metrics). Labels are route templates, never ids; a series nobody touched for a week disappears.')}
        actions={
          <>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={auto} onCheckedChange={setAuto} /> {t('Auto-refresh')}
            </label>
            <Button variant="outline" size="sm" onClick={() => q.refetch()} disabled={q.isFetching}>
              <RefreshCwIcon className={q.isFetching ? 'animate-spin' : ''} /> {t('Refresh')}
            </Button>
          </>
        }
      />
      {q.isError ? (
        <ErrorBox error={q.error} onRetry={() => q.refetch()} />
      ) : (
        <Tabs defaultValue="table" className="min-h-0 flex-1 gap-3">
          <TabsList>
            <TabsTrigger value="table">{t('Samples')}</TabsTrigger>
            <TabsTrigger value="raw">{t('Raw')}</TabsTrigger>
          </TabsList>
          <TabsContent value="table" className="flex min-h-0 flex-1 flex-col">
            <DataTable
              columns={columns}
              data={q.data === undefined ? undefined : rows}
              loading={q.isLoading}
              searchPlaceholder={t('Filter samples…')}
              pageSize={50}
              toolbar={
                <InputGroup className="w-56">
                  <InputGroupAddon>
                    <InputGroupText>{t('Name')}</InputGroupText>
                  </InputGroupAddon>
                  <InputGroupInput aria-label={t('Metric name prefix')} placeholder={t('prefix…')} value={prefix} onChange={(e) => setPrefix(e.target.value)} />
                </InputGroup>
              }
            />
          </TabsContent>
          <TabsContent value="raw" className="min-h-0 flex-1 overflow-auto rounded-xl border bg-card p-3">
            <pre className="value-mono">{q.data}</pre>
          </TabsContent>
        </Tabs>
      )}
    </Page>
  )
}

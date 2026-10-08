import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { DownloadIcon, FileJsonIcon, UploadIcon } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Spinner } from '@/components/ui/spinner'
import { FormDialog } from '@/components/dialogs'
import { FormField } from '@/components/form'
import { api } from '@/lib/api'
import { downloadText, knowledgeJson, parseKnowledgeJson } from '@/lib/kb-json'
import { errorMessage } from '@/lib/queries'
import type { Agent } from '@/lib/types'

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'agent'

/** Downloads every entry of the agent as a JSON array of strings. */
export function ExportButton({ agent }: { agent: Agent | undefined }) {
  const [busy, setBusy] = useState(false)
  async function run() {
    if (!agent) return
    setBusy(true)
    try {
      const entries = await api.allRag(agent.id)
      downloadText(`knowledge-${slug(agent.name)}.json`, knowledgeJson(entries.map((e) => e.content ?? '')))
      toast.success(entries.length ? `Exported ${entries.length} ${entries.length === 1 ? 'entry' : 'entries'}` : 'The knowledge base is empty: exported an empty list')
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Button variant="outline" disabled={!agent || busy} onClick={run}>
      {busy ? <Spinner /> : <DownloadIcon />} Export JSON
    </Button>
  )
}

const CONCURRENCY = 4

/** Adds the strings of a JSON file to the knowledge base of the agent, one entry each (existing entries stay). */
export function ImportDialog({ agent, open, onClose }: { agent: Agent | undefined; open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<string | null>(null)
  const [items, setItems] = useState<string[] | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [done, setDone] = useState(0)
  const [failures, setFailures] = useState<{ index: number; error: string }[]>([])
  const [running, setRunning] = useState(false)

  function reset() {
    setFile(null)
    setItems(null)
    setProblem(null)
    setDone(0)
    setFailures([])
  }
  function close() {
    if (running) return
    reset()
    onClose()
  }

  async function pick(f: File | undefined) {
    reset()
    if (!f) return
    setFile(f.name)
    const parsed = parseKnowledgeJson(await f.text())
    if (parsed.ok) setItems(parsed.items)
    else setProblem(parsed.error)
  }

  async function run() {
    if (!agent || !items) return
    setRunning(true)
    setDone(0)
    setFailures([])
    const failed: { index: number; error: string }[] = []
    let next = 0
    let finished = 0
    const worker = async () => {
      while (next < items.length) {
        const i = next++
        try {
          await api.createRag({ content: items[i] }, agent.id)
        } catch (e) {
          failed.push({ index: i + 1, error: errorMessage(e) })
        }
        setDone(++finished)
      }
    }
    await Promise.all(Array.from({ length: Math.min(CONCURRENCY, items.length) }, worker))
    failed.sort((a, b) => a.index - b.index)
    setFailures(failed)
    setRunning(false)
    qc.invalidateQueries({ queryKey: ['rag'] })
    const ok = items.length - failed.length
    if (!failed.length) {
      toast.success(`Imported ${ok} ${ok === 1 ? 'entry' : 'entries'}`)
      reset()
      onClose()
    } else {
      toast.error(`Imported ${ok} of ${items.length}; ${failed.length} failed`)
    }
  }

  return (
    <FormDialog
      open={open}
      onClose={close}
      title="Import knowledge"
      description={
        <>
          A JSON array of strings, for example <code>{'["Refunds take 5 days.", "We ship worldwide."]'}</code>. Each string becomes an entry of {agent ? `“${agent.name}”` : 'the agent'}; entries already there stay.
        </>
      }
      submitLabel={items ? `Import ${items.length} ${items.length === 1 ? 'entry' : 'entries'}` : 'Import'}
      onSubmit={run}
      submitDisabled={!items || !agent || running || (failures.length > 0 && done === items.length)}
      pending={running}
      problem={problem}
    >
      <div className="grid gap-4">
        <FormField label="JSON file">
          <input
            ref={input}
            type="file"
            accept="application/json,.json"
            disabled={running}
            onChange={(e) => pick(e.target.files?.[0])}
            className="block w-full cursor-pointer rounded-lg border bg-background text-sm file:mr-3 file:cursor-pointer file:border-0 file:bg-muted file:px-3 file:py-2 file:text-sm file:font-medium"
          />
        </FormField>
        {items && !running && !failures.length && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <FileJsonIcon className="size-4" /> {file}: {items.length} {items.length === 1 ? 'entry' : 'entries'} ready.
          </p>
        )}
        {(running || failures.length > 0) && items && (
          <div className="grid gap-2">
            <Progress value={(done / items.length) * 100} aria-label="Import progress" />
            <p className="text-sm text-muted-foreground">
              {running ? `Importing… ${done} of ${items.length}` : `Imported ${items.length - failures.length} of ${items.length}.`}
            </p>
          </div>
        )}
        {failures.length > 0 && (
          <div className="grid gap-1 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm" role="alert">
            <p className="font-medium text-destructive">{failures.length} could not be imported</p>
            <ul className="max-h-40 overflow-auto text-muted-foreground">
              {failures.slice(0, 20).map((f) => (
                <li key={f.index}>
                  Item {f.index}: {f.error}
                </li>
              ))}
              {failures.length > 20 && <li>…and {failures.length - 20} more</li>}
            </ul>
          </div>
        )}
      </div>
    </FormDialog>
  )
}

export function ImportButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  return (
    <Button variant="outline" disabled={disabled} onClick={onClick}>
      <UploadIcon /> Import JSON
    </Button>
  )
}

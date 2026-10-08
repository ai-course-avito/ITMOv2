import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { FieldGroup, FieldLegend, FieldSeparator, FieldSet } from '@/components/ui/field'
import { AgentForm, configFrom, draftFrom, emptyDraft, validateDraft, type AgentDraft } from '@/components/agent-form'
import { FormDialog } from '@/components/dialogs'
import { CheckboxField } from '@/components/form'
import { LoadingRows } from '@/components/page'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useMcpServers } from '@/lib/data'
import { errorMessage, useAction } from '@/lib/queries'
import { NAME_MAX, type Agent } from '@/lib/types'

export type AgentDialogMode = { kind: 'create' } | { kind: 'edit'; agent: Agent } | { kind: 'duplicate'; agent: Agent }

/** Create, edit or duplicate an agent, including which MCP servers are attached. */
export function AgentDialog({ mode, onClose }: { mode: AgentDialogMode | null; onClose: () => void }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const open = mode !== null
  const source = mode && mode.kind !== 'create' ? mode.agent : null
  const editId = mode?.kind === 'edit' ? mode.agent.id : null

  const { isAdmin } = useAuth()
  const servers = useMcpServers()
  const attached = useQuery({ queryKey: ['agent-mcp', source?.id], queryFn: () => api.agentMcpServers(source!.id), enabled: open && source !== null, staleTime: 0 })
  const versions = useQuery({ queryKey: ['versions', editId], queryFn: () => api.versions(editId!), enabled: open && editId !== null, staleTime: 0 })

  const [draft, setDraft] = useState<AgentDraft>(emptyDraft)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!open) {
      setReady(false)
      return
    }
    if (source === null) {
      setDraft(emptyDraft)
      setSelected(new Set())
      setReady(true)
    } else if (attached.data) {
      setDraft(mode?.kind === 'duplicate' ? { ...draftFrom(source), name: `${source.name} (copy)`.slice(0, NAME_MAX) } : draftFrom(source))
      setSelected(new Set(attached.data.map((s) => s.id)))
      setReady(true)
    }
  }, [open, source, attached.data])

  const save = useAction(
    async () => {
      let agent: Agent
      if (editId !== null) {
        agent = await api.updateAgent(editId, {
          ...(draft.name.trim() !== source!.name ? { name: draft.name.trim() } : {}),
          prompt: draft.prompt,
          model_id: Number(draft.modelId),
          config: configFrom(draft, 'update', source!.config),
          comment: draft.comment || null,
          expected_version: versions.data?.[0]?.number, // optimistic lock
        })
      } else {
        agent = await api.createAgent({
          name: draft.name.trim(),
          prompt: draft.prompt,
          model_id: Number(draft.modelId),
          config: configFrom(draft, 'create'),
          comment: draft.comment || (mode?.kind === 'duplicate' ? `copy of agent ${source!.id}` : null),
        })
      }
      // MCP attachments: only the difference from what is attached now
      const before = new Set(editId !== null ? (attached.data ?? []).map((s) => s.id) : [])
      try {
        if (isAdmin) for (const id of selected) if (!before.has(id)) await api.attachMcpServer(agent.id, id)
        if (isAdmin) for (const id of before) if (!selected.has(id)) await api.detachMcpServer(agent.id, id)
      } catch (e) {
        toast.error(`The agent was saved, but its MCP servers were not fully updated: ${errorMessage(e)}`)
      }
      return agent
    },
    {
      success: (a) => (editId !== null ? `Agent “${a.name}” saved` : `Agent “${a.name}” created`),
      onSuccess: (a) => {
        for (const key of ['agents', 'agent', 'versions', 'agent-mcp', 'self-agent']) qc.invalidateQueries({ queryKey: [key] })
        onClose()
        if (editId === null) navigate(`/agents/${a.id}`)
      },
    },
  )

  const problem = validateDraft(draft)
  const title = mode?.kind === 'edit' ? `Edit agent “${mode.agent.name}”` : mode?.kind === 'duplicate' ? `Duplicate agent “${mode.agent.name}”` : 'New agent'

  return (
    <FormDialog
      open={open}
      onClose={onClose}
      title={title}
      description="A prompt, a model, tools, limits and the MCP servers the agent may call. Every change is recorded as a version."
      size="lg"
      submitLabel={editId !== null ? 'Save' : 'Create'}
      onSubmit={() => save.mutate(undefined)}
      submitDisabled={!ready || !!problem}
      pending={save.isPending}
      problem={problem}
    >
      {!ready ? (
        <LoadingRows rows={5} />
      ) : (
        <FieldGroup>
          <AgentForm draft={draft} onChange={setDraft} />
          {isAdmin && <FieldSeparator />}
          {isAdmin && (
          <FieldSet>
            <FieldLegend>MCP servers</FieldLegend>
            <FieldGroup className="gap-3 rounded-lg border p-3">
              {(servers.data ?? []).map((s) => (
                <CheckboxField
                  key={s.id}
                  label={`${s.name} (${String(s.config.url ?? "")})`}
                  checked={selected.has(s.id)}
                  onCheckedChange={(v) =>
                    setSelected((cur) => {
                      const n = new Set(cur)
                      if (v) n.add(s.id)
                      else n.delete(s.id)
                      return n
                    })
                  }
                />
              ))}
              {!servers.data?.length && <span className="text-sm text-muted-foreground">No MCP servers exist yet. Create them on the MCP servers page.</span>}
            </FieldGroup>
          </FieldSet>
          )}
        </FieldGroup>
      )}
    </FormDialog>
  )
}

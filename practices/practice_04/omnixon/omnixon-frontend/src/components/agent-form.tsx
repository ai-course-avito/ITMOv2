import { BrainCircuitIcon, BrainIcon, SettingsIcon } from 'lucide-react'
import { FieldGroup, FieldLegend, FieldSeparator, FieldSet } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { CheckboxField, FormField, OptionCombobox, OptionSelect, SwitchField } from '@/components/form'
import { useModels } from '@/lib/data'
import { modelOption } from '@/lib/options'
import { AVAILABLE_TOOLS, NAME_MAX, type AgentConfig, type AgentConfigInput } from '@/lib/types'

export interface AgentDraft {
  name: string
  prompt: string
  modelId: string | null
  customTools: boolean
  tools: string[]
  messageLimit: string
  memoLimit: string
  ragLimit: string
  autoMemory: 'default' | 'on' | 'off'
  comment: string
}

const DEFAULT_TOOLS = ['rag', 'memory']
const sameTools = (a: string[], b: string[]) => a.length === b.length && a.every((t) => b.includes(t))

export const emptyDraft: AgentDraft = {
  name: '',
  prompt: '',
  modelId: '0',
  customTools: false,
  tools: DEFAULT_TOOLS,
  messageLimit: '',
  memoLimit: '',
  ragLimit: '',
  autoMemory: 'default',
  comment: '',
}

export function draftFrom(a: { name: string; prompt: string; model_id: number; config: AgentConfig }): AgentDraft {
  const c = a.config
  return {
    name: a.name,
    prompt: a.prompt,
    modelId: String(a.model_id),
    // The service always returns `tools` (rag + memory when unset), so a list equal to
    // the default cannot be told from an unset one; both behave the same.
    customTools: c.tools !== undefined && !sameTools(c.tools, DEFAULT_TOOLS),
    tools: c.tools ?? DEFAULT_TOOLS,
    messageLimit: c.message_limit !== undefined ? String(c.message_limit) : '',
    memoLimit: c.memo_limit !== undefined ? String(c.memo_limit) : '',
    ragLimit: c.rag_limit !== undefined ? String(c.rag_limit) : '',
    autoMemory: c.auto_memory === undefined ? 'default' : c.auto_memory ? 'on' : 'off',
    comment: '',
  }
}

/** On create only the given keys are sent; on update every key is sent and `null` resets it to the default. */
export function configFrom(d: AgentDraft, mode: 'create' | 'update', original?: AgentConfig): AgentConfigInput {
  const cfg: AgentConfigInput = {}
  const put = <K extends keyof AgentConfig>(key: K, value: AgentConfig[K] | undefined) => {
    if (value !== undefined) cfg[key] = value
    else if (mode === 'update') cfg[key] = null
  }
  // an untouched default list is left alone: resetting it would only add noise to the versions
  if (d.customTools || mode === 'create' || !original?.tools || !sameTools(original.tools, DEFAULT_TOOLS)) {
    put('tools', d.customTools ? d.tools : undefined)
  }
  put('message_limit', d.messageLimit.trim() === '' ? undefined : Number(d.messageLimit))
  put('memo_limit', d.memoLimit.trim() === '' ? undefined : Number(d.memoLimit))
  put('rag_limit', d.ragLimit.trim() === '' ? undefined : Number(d.ragLimit))
  put('auto_memory', d.autoMemory === 'default' ? undefined : d.autoMemory === 'on')
  return cfg
}

export function validateDraft(d: AgentDraft): string | null {
  if (!d.name.trim()) return 'Give the agent a name'
  if (d.modelId === null) return 'Choose a model'
  const ml = d.messageLimit.trim()
  if (ml !== '' && !(Number.isInteger(Number(ml)) && Number(ml) >= 0 && Number(ml) <= 1000))
    return 'Message limit must be an integer from 0 to 1000'
  const mo = d.memoLimit.trim()
  if (mo !== '' && !(Number.isInteger(Number(mo)) && Number(mo) >= 1 && Number(mo) <= 1000))
    return 'Memory limit must be an integer from 1 to 1000'
  const rl = d.ragLimit.trim()
  if (rl !== '' && !(Number.isInteger(Number(rl)) && Number(rl) >= 1 && Number(rl) <= 100))
    return 'Knowledge limit must be an integer from 1 to 100'
  return null
}

function useSetter(draft: AgentDraft, onChange: (d: AgentDraft) => void) {
  return (patch: Partial<AgentDraft>) => onChange({ ...draft, ...patch })
}

interface PartProps {
  draft: AgentDraft
  onChange: (d: AgentDraft) => void
}

/** The prompt and the model: what the agent is. */
export function AgentBasics({ draft, onChange }: PartProps) {
  const models = useModels()
  const set = useSetter(draft, onChange)
  const modelOptions = (models.data ?? []).map(modelOption)
  return (
    <FieldGroup>
      <FormField label="Name">
        <Input
          maxLength={NAME_MAX}
          value={draft.name}
          onChange={(e) => set({ name: e.target.value })}
          placeholder="Support bot"
        />
      </FormField>
      <FormField label="System prompt">
        <Textarea
          rows={10}
          value={draft.prompt}
          onChange={(e) => set({ prompt: e.target.value })}
          placeholder="You are a helpful assistant…"
        />
      </FormField>
      <FormField label="Model">
        <OptionCombobox
          value={draft.modelId}
          onChange={(v) => set({ modelId: v })}
          options={modelOptions}
          placeholder="Select a model"
        />
      </FormField>
    </FieldGroup>
  )
}

/** Tools, limits and auto memory: how the agent works. */
export function AgentSettings({ draft, onChange }: PartProps) {
  const set = useSetter(draft, onChange)
  return (
    <FieldGroup className="gap-4">
      <SwitchField
        label="Custom tools"
        description="Default: rag and memory."
        checked={draft.customTools}
        onCheckedChange={(v) => set({ customTools: v })}
      />
      {draft.customTools && (
        <FieldGroup className="gap-3 pl-1">
          {AVAILABLE_TOOLS.map((t) => (
            <CheckboxField
              key={t}
              label={t}
              checked={draft.tools.includes(t)}
              onCheckedChange={(v) => set({ tools: v ? [...draft.tools, t] : draft.tools.filter((x) => x !== t) })}
            />
          ))}
        </FieldGroup>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Message limit" description="Latest messages given to the model. Empty = service default.">
          <Input
            type="number"
            min={0}
            max={1000}
            value={draft.messageLimit}
            onChange={(e) => set({ messageLimit: e.target.value })}
            placeholder="default"
          />
        </FormField>
        <FormField label="Memory limit" description="Memories shown at once (at least 1). Empty = service default.">
          <Input
            type="number"
            min={1}
            max={1000}
            value={draft.memoLimit}
            onChange={(e) => set({ memoLimit: e.target.value })}
            placeholder="default"
          />
        </FormField>
        <FormField
          label="Knowledge limit"
          description="Knowledge base entries one search returns (1 to 100). Empty = service default (8)."
        >
          <Input
            type="number"
            min={1}
            max={100}
            value={draft.ragLimit}
            onChange={(e) => set({ ragLimit: e.target.value })}
            placeholder="default"
          />
        </FormField>
      </div>
      <FormField label="Auto memory" description="After a saved exchange, one more model call extracts lasting facts.">
        <OptionSelect
          value={draft.autoMemory}
          onChange={(v) => set({ autoMemory: v as AgentDraft['autoMemory'] })}
          options={[
            {
              value: 'default',
              label: 'Service default',
              icon: SettingsIcon,
              description: 'Whatever the service is set to (on, unless its DEFAULT_AUTO_MEMORY says otherwise)',
            },
            {
              value: 'on',
              label: 'On',
              icon: BrainIcon,
              description: 'Learn lasting facts after every saved exchange',
            },
            {
              value: 'off',
              label: 'Off',
              icon: BrainCircuitIcon,
              description: 'Remember only what the model itself saves with its tool',
            },
          ]}
        />
      </FormField>
    </FieldGroup>
  )
}

export function AgentComment({ draft, onChange }: PartProps) {
  const set = useSetter(draft, onChange)
  return (
    <FormField label="Comment" description="Shown in the version history of the agent.">
      <Input value={draft.comment} onChange={(e) => set({ comment: e.target.value })} placeholder="What and why" />
    </FormField>
  )
}

/** All of it, stacked: for the dialogs. */
export function AgentForm({ draft, onChange }: PartProps) {
  return (
    <FieldGroup>
      <AgentBasics draft={draft} onChange={onChange} />
      <FieldSeparator />
      <FieldSet>
        <FieldLegend>Configuration</FieldLegend>
        <AgentSettings draft={draft} onChange={onChange} />
      </FieldSet>
      <FieldSeparator />
      <AgentComment draft={draft} onChange={onChange} />
    </FieldGroup>
  )
}

import { useSearchParams } from 'react-router-dom'
import { FormField, OptionCard, OptionCombobox } from '@/components/form'
import { useAgents, useModels, useSelfAgent } from '@/lib/data'
import { useAuth } from '@/lib/auth'
import { t } from '@/lib/i18n'
import { agentOption, withoutLinks } from '@/lib/options'

/**
 * Which agent a page is about. A token works as its own agent; an admin or owner may pick another one (the
 * page then sends `X-Act-As-Agent`). The choice lives in the URL (`?agent=`), so it can be linked to, and it
 * starts on the agent of the token. Anyone else just has their own.
 */
export function useActingAgent() {
  const { agentId: own, isAdmin } = useAuth()
  const [params, setParams] = useSearchParams()
  const asked = isAdmin ? Number(params.get('agent')) || undefined : undefined
  const agentId = asked ?? own
  const choose = (id: string, drop: string[] = []) =>
    setParams((p) => {
      const next = new URLSearchParams(p)
      for (const key of drop) next.delete(key)
      if (Number(id) === own) next.delete('agent')
      else next.set('agent', id)
      return next
    })
  return {
    agentId,
    /** What to send as `X-Act-As-Agent`: only when it is not the agent of the token. */
    actAs: agentId !== undefined && agentId !== own ? agentId : undefined,
    own: agentId === own,
    choose,
  }
}

/** The agent of the page: a picker of cards for an admin, the own agent as a card for everybody else. */
export function AgentField({
  label = t('Agent'),
  description,
  className,
  agentId,
  onChange,
}: {
  label?: string
  description?: string
  className?: string
  agentId: number | undefined
  onChange: (id: string) => void
}) {
  const { isAdmin, role } = useAuth()
  const agents = useAgents()
  const models = useModels()
  const self = useSelfAgent()
  if (isAdmin) {
    return (
      <FormField label={label} description={description} className={className}>
        <OptionCombobox
          value={agentId !== undefined ? String(agentId) : null}
          onChange={onChange}
          options={(agents.data ?? []).map((a) => agentOption(a, models.data))}
          placeholder={t('Select an agent')}
        />
      </FormField>
    )
  }
  const own = self.data
  return (
    <FormField label={label} description={description} className={className}>
      <div className="min-h-10 rounded-lg border bg-background p-1.5">
        {own ? <OptionCard compact option={role === 'user' ? agentOption(own, models.data) : withoutLinks(agentOption(own))} /> : <span className="px-1 text-sm text-muted-foreground">{t('Loading…')}</span>}
      </div>
    </FormField>
  )
}

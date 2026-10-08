import { PaperclipIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { CopyButton } from '@/components/display'
import { Markdown } from '@/components/markdown'
import { cn } from '@/lib/utils'
import { fmtDate } from '@/lib/format'
import type { Message } from '@/lib/types'

function asText(content: unknown): string {
  if (typeof content === 'string') return content
  return JSON.stringify(content, null, 2)
}

export function MessageBubble({ message }: { message: Message }) {
  const role = message.content.type === 'user' ? 'user' : 'assistant'
  const notes = (message.content.attachments ?? []) as unknown[]
  return (
    <div className={cn('flex flex-col gap-1', role === 'user' ? 'items-end' : 'items-start')}>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="font-medium">{role}</span>
        <span>{fmtDate(message.timestamp)}</span>
        {message.content.interrupted === true && <Badge variant="outline">interrupted</Badge>}
        {message.agent_version != null && <Badge variant="outline">agent v{message.agent_version}</Badge>}
      </div>
      <div className={cn('max-w-[85%] min-w-0 rounded-xl px-3 py-2 text-sm', role === 'user' ? 'whitespace-pre-wrap bg-primary text-primary-foreground' : 'bg-muted')}>
        {role === 'user' ? asText(message.content.content) : <Markdown>{asText(message.content.content)}</Markdown>}
      </div>
      {role === 'assistant' && <CopyButton text={asText(message.content.content)} label="Copy answer" />}
      {notes.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {notes.map((n, i) => (
            <Badge key={i} variant="secondary">
              <PaperclipIcon /> {typeof n === 'string' ? n : JSON.stringify(n)}
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}

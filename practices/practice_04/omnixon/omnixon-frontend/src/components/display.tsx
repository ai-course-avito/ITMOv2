import { useState } from 'react'
import { CheckIcon, CopyIcon, EyeIcon, EyeOffIcon } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { maskToken, pretty } from '@/lib/format'
import { t } from '@/lib/i18n'
import { cn } from '@/lib/utils'

export function CopyButton({ text, label = t('Copy') }: { text: string; label?: string }) {
  const [done, setDone] = useState(false)
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      aria-label={label}
      title={label}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text)
          setDone(true)
          setTimeout(() => setDone(false), 1200)
        } catch {
          toast.error(t('Clipboard is not available'))
        }
      }}
    >
      {done ? <CheckIcon /> : <CopyIcon />}
    </Button>
  )
}

/** A token that is masked until asked for, with show and copy buttons. */
export function SecretValue({ value, revealed, onToggle }: { value: string; revealed: boolean; onToggle: () => void }) {
  return (
    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
      <code className="value-mono">{revealed ? value : maskToken(value)}</code>
      <Button type="button" variant="ghost" size="icon-sm" aria-label={revealed ? t('Hide token') : t('Show token')} onClick={onToggle}>
        {revealed ? <EyeOffIcon /> : <EyeIcon />}
      </Button>
      <CopyButton text={value} label={t('Copy token')} />
    </div>
  )
}

export function JsonView({ value, className }: { value: unknown; className?: string }) {
  return <pre className={cn('max-h-96 overflow-auto rounded-lg border bg-muted/40 p-3 font-mono text-xs leading-relaxed', className)}>{pretty(value)}</pre>
}

import { useEffect, useState } from 'react'
import { CheckIcon, CopyIcon } from 'lucide-react'
import { toast } from 'sonner'
import { highlight, languageOf } from '@/lib/highlight'
import { t } from '@/lib/i18n'
import { cn } from '@/lib/utils'

const NAMES: Record<string, string> = { javascript: 'JavaScript', typescript: 'TypeScript', jsx: 'JSX', tsx: 'TSX', json: 'JSON', jsonc: 'JSON', bash: 'Shell', shellscript: 'Shell', sql: 'SQL', yaml: 'YAML', html: 'HTML', css: 'CSS', markdown: 'Markdown', diff: 'Diff', python: 'Python', go: 'Go', rust: 'Rust', java: 'Java', c: 'C', cpp: 'C++', csharp: 'C#', php: 'PHP', ruby: 'Ruby', kotlin: 'Kotlin', swift: 'Swift', toml: 'TOML', dockerfile: 'Dockerfile', xml: 'XML' }

/**
 * Code as GitHub shows it: a box with the language and a copy button above, and the code coloured by token (the colours
 * are CSS variables, so the box follows the theme). A language we do not colour, or none, is shown plain, in the same box.
 */
export function CodeBlock({ code, lang, className }: { code: string; lang?: string | null; className?: string }) {
  const [html, setHtml] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const known = languageOf(lang)

  useEffect(() => {
    let current = true
    highlight(code, lang)
      .then((h) => current && setHtml(h))
      .catch(() => current && setHtml(null)) // the code is shown plain rather than not at all
    return () => {
      current = false
    }
  }, [code, lang])

  async function copy() {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    } catch {
      toast.error(t('Clipboard is not available'))
    }
  }

  const label = known ? (NAMES[known] ?? known) : lang?.trim() ? lang.trim() : 'text'
  return (
    <div data-slot="code-block" className={cn('my-3 overflow-hidden rounded-lg border bg-muted/40 text-left', className)}>
      <div className="flex items-center justify-between border-b bg-muted/60 py-1 pr-1 pl-3 text-xs text-muted-foreground">
        <span className="font-medium">{label}</span>
        <button
          type="button"
          onClick={copy}
          aria-label={t('Copy code')}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 transition-colors hover:bg-background hover:text-foreground"
        >
          {copied ? <CheckIcon className="size-3.5" /> : <CopyIcon className="size-3.5" />}
          {copied ? t('Copied') : t('Copy')}
        </button>
      </div>
      <div className="code-body">
        {html ? (
          <div dangerouslySetInnerHTML={{ __html: html }} />
        ) : (
          <pre className="m-0 overflow-x-auto px-4 py-3 text-[0.8125rem] leading-relaxed">
            <code className="font-mono">{code}</code>
          </pre>
        )}
      </div>
    </div>
  )
}

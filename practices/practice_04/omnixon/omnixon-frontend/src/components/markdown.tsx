import { isValidElement, type ComponentProps, type ReactElement, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import 'katex/dist/katex.min.css'
import 'katex/contrib/mhchem' // \ce{H2O}, \pu{...}: the chemistry a model likes to write
import { CodeBlock } from '@/components/code-block'
import { prepareMath } from '@/lib/math'
import { cn } from '@/lib/utils'

/** The text of a code element's children (react-markdown gives a string, or a list of them). */
function textOf(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (isValidElement(node)) return textOf((node as ReactElement<{ children?: ReactNode }>).props.children)
  return ''
}

/** A formula KaTeX cannot read is shown as its source, quietly (not in red); the commands a model uses that KaTeX lacks are defined here. */
const KATEX = {
  throwOnError: false,
  strict: 'ignore',
  trust: false,
  errorColor: 'var(--muted-foreground)',
  macros: { '\\degree': '^{\\circ}', '\\celsius': '^{\\circ}\\mathrm{C}', '\\R': '\\mathbb{R}', '\\N': '\\mathbb{N}', '\\Z': '\\mathbb{Z}', '\\Q': '\\mathbb{Q}', '\\C': '\\mathbb{C}', '\\vect': '\\mathbf{#1}', '\\abs': '\\left|#1\\right|', '\\norm': '\\left\\|#1\\right\\|' },
} as const

const components: ComponentProps<typeof ReactMarkdown>['components'] = {
  // a fenced block: ```lang ... ```
  pre({ children }) {
    const code = isValidElement(children) ? (children as ReactElement<{ className?: string; children?: ReactNode }>) : null
    const lang = /language-(\S+)/.exec(code?.props.className ?? '')?.[1]
    return <CodeBlock code={textOf(code?.props.children ?? children).replace(/\n$/, '')} lang={lang} />
  },
  // `inline code` (fenced blocks never get here: `pre` takes them)
  code({ className, children }) {
    return <code className={cn('rounded-md border bg-muted px-1.5 py-0.5 font-mono text-[0.85em]', className)}>{children}</code>
  },
  a({ href, children }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="font-medium text-foreground underline underline-offset-4 hover:text-muted-foreground">
        {children}
      </a>
    )
  },
  // an image would make the browser fetch whatever address a model wrote: show where it points instead
  img({ alt, src }) {
    return (
      <a href={src} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4">
        {alt || 'image'}
      </a>
    )
  },
  p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
  h1: ({ children }) => <h1 className="mt-4 mb-2 text-xl font-semibold first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mt-4 mb-2 border-b pb-1 text-lg font-semibold first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mt-3 mb-1.5 text-base font-semibold first:mt-0">{children}</h3>,
  h4: ({ children }) => <h4 className="mt-3 mb-1 text-sm font-semibold first:mt-0">{children}</h4>,
  ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-6 marker:text-muted-foreground">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-6 marker:text-muted-foreground">{children}</ol>,
  li: ({ children }) => <li className="[&>ol]:my-1 [&>p]:my-0 [&>ul]:my-1">{children}</li>,
  blockquote: ({ children }) => <blockquote className="my-2 border-l-4 pl-3 text-muted-foreground">{children}</blockquote>,
  hr: () => <hr className="my-4 border-border" />,
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-lg border">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-muted/60">{children}</thead>,
  th: ({ children }) => <th className="border-b px-3 py-1.5 text-left font-medium">{children}</th>,
  td: ({ children }) => <td className="border-b px-3 py-1.5 last:border-0">{children}</td>,
  input: (props) => <input {...props} disabled className="mr-1.5 align-middle" />, // task lists
}

/**
 * What a model wrote, rendered: GitHub-flavoured markdown (tables, task lists, strikethrough), formulas in LaTeX (`$O(\log n)$`,
 * `$$...$$`, `\(...\)`, `\[...\]`, drawn by KaTeX), links that open in a new tab, and fenced code coloured like on GitHub. Raw HTML in the text is shown as text, never run.
 */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div data-slot="markdown" className={cn('min-w-0 text-sm leading-relaxed break-words', className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[[rehypeKatex, KATEX]]} components={components}>
        {prepareMath(children)}
      </ReactMarkdown>
    </div>
  )
}

import type { ComponentType, FormEvent, ReactNode } from 'react'
import { RefreshCwIcon, TriangleAlertIcon } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Skeleton } from '@/components/ui/skeleton'
import { t } from '@/lib/i18n'
import { errorMessage } from '@/lib/queries'
import { cn } from '@/lib/utils'

/** The page: a column that fills the space the layout gives it. */
export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('flex min-h-0 flex-1 flex-col gap-4', className)}>{children}</div>
}

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

/** The body of a page that is not one big table: it scrolls inside the page, not the page itself.
 *  The 1px of padding (undone by the negative margin) is room for the ring of a card, which a scroll container would cut off. */
export function PageScroll({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('-m-px min-h-0 flex-1 overflow-auto p-px', className)}>{children}</div>
}

/**
 * The bar above a list that is asked for something (an agent, a user, a search text):
 * the same card on every page, controls in a row, the action on the right.
 */
export function QueryBar({ onSubmit, children, actions }: { onSubmit: () => void; children: ReactNode; actions?: ReactNode }) {
  function submit(e: FormEvent) {
    e.preventDefault()
    onSubmit()
  }
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3 rounded-xl border bg-card p-3 shadow-xs">
      {children}
      {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
    </form>
  )
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ComponentType<{ className?: string }>
  title: string
  description?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <Empty className={cn('border border-dashed', className)}>
      <EmptyHeader>
        {Icon && (
          <EmptyMedia variant="icon">
            <Icon />
          </EmptyMedia>
        )}
        <EmptyTitle>{title}</EmptyTitle>
        {description && <EmptyDescription>{description}</EmptyDescription>}
      </EmptyHeader>
      {action && <EmptyContent>{action}</EmptyContent>}
    </Empty>
  )
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <Alert variant="destructive">
      <TriangleAlertIcon />
      <AlertTitle>{t('Request failed')}</AlertTitle>
      <AlertDescription>
        <p>{errorMessage(error)}</p>
        {onRetry && (
          <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
            <RefreshCwIcon /> {t('Retry')}
          </Button>
        )}
      </AlertDescription>
    </Alert>
  )
}

export function LoadingRows({ rows = 4, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn('grid gap-2', className)}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  )
}

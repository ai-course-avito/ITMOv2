import { cn } from '@/lib/utils'

/** The mark of the panel. It is the favicon itself (public/favicon.svg), so there is one drawing. */
export function Logo({ className }: { className?: string }) {
  return <img src="/favicon.svg" alt="Omnixon" draggable={false} className={cn('size-8 shrink-0 select-none', className)} />
}

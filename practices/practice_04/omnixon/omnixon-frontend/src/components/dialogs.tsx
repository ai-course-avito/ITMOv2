import type { FormEvent, ReactNode } from 'react'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Spinner } from '@/components/ui/spinner'
import { t } from '@/lib/i18n'
import { cn } from '@/lib/utils'

const SIZES = { sm: 'sm:max-w-md', md: 'sm:max-w-xl', lg: 'sm:max-w-3xl' } as const

interface FormDialogProps {
  open: boolean
  onClose: () => void
  title: string
  description?: ReactNode
  /** md fits a form of a few fields, lg is for prompts and JSON. */
  size?: keyof typeof SIZES
  children: ReactNode
  submitLabel?: string
  /** Called on the submit button and on Enter; leave out for a dialog that only shows something. */
  onSubmit?: () => void
  submitDisabled?: boolean
  pending?: boolean
  /** Shown above the buttons, e.g. a validation message. */
  problem?: ReactNode
  /** Extra buttons on the left of the footer. */
  footerStart?: ReactNode
}

/** Every dialog of the panel: the same header, scrolling body and footer. */
export function FormDialog({
  open,
  onClose,
  title,
  description,
  size = 'md',
  children,
  submitLabel = t('Save'),
  onSubmit,
  submitDisabled,
  pending,
  problem,
  footerStart,
}: FormDialogProps) {
  function submit(e: FormEvent) {
    e.preventDefault()
    if (!submitDisabled && !pending) onSubmit?.()
  }
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className={cn('flex max-h-[90vh] flex-col gap-0 overflow-hidden p-0', SIZES[size])}>
        <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
          <DialogHeader className="px-5 pt-5 pb-3">
            <DialogTitle>{title}</DialogTitle>
            {description && <DialogDescription>{description}</DialogDescription>}
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 pt-2 pb-6">{children}</div>
          {problem && <p className="px-5 pt-2 text-sm text-destructive">{problem}</p>}
          {/* DialogFooter pulls itself out by the padding of a p-4 dialog; this one has none */}
          <DialogFooter className="mx-0 mb-0 items-center rounded-none px-5 py-3 sm:justify-between">
            <div className="flex items-center gap-2">{footerStart}</div>
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                {onSubmit ? t('Cancel') : t('Close')}
              </Button>
              {onSubmit && (
                <Button type="submit" disabled={submitDisabled || pending}>
                  {pending && <Spinner />} {submitLabel}
                </Button>
              )}
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = t('Delete'),
  destructive = true,
  pending,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: ReactNode
  confirmLabel?: string
  destructive?: boolean
  pending?: boolean
  onConfirm: () => void
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{t('Cancel')}</AlertDialogCancel>
          <AlertDialogAction variant={destructive ? 'destructive' : 'default'} disabled={pending} onClick={onConfirm}>
            {pending && <Spinner />} {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

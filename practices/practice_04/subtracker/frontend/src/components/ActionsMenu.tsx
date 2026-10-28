import { useEffect, useId, useRef, useState } from 'react'
import { useT } from '../i18n'
import { Dots } from './Icons'

interface Props {
  name: string
  isActive: boolean
  onEdit: () => void
  onToggle: () => void
  onDelete: () => void
}

export function ActionsMenu({ name, isActive, onEdit, onToggle, onDelete }: Props) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const menuId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        buttonRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const run = (action: () => void) => () => {
    setOpen(false)
    action()
  }
  const item = 'block w-full rounded-xl px-3.5 py-2.5 text-left text-sm text-text hover:bg-surface2'

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-label={`${t.common.actions}: ${name}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((v) => !v)}
        className="flex size-8 shrink-0 cursor-pointer md:size-9 items-center justify-center rounded-full border-0 bg-transparent text-muted"
      >
        <Dots />
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          className="absolute top-10 right-0 z-30 w-56 rounded-2xl border border-line bg-surface p-1.5 shadow-xl"
        >
          <button type="button" role="menuitem" className={item} onClick={run(onEdit)}>{t.common.edit}</button>
          <button type="button" role="menuitem" className={item} onClick={run(onToggle)}>
            {isActive ? t.common.pause : t.common.resume}
          </button>
          <button type="button" role="menuitem" className={`${item} text-red-400`} onClick={run(onDelete)}>
            {t.common.delete}
          </button>
        </div>
      )}
    </div>
  )
}

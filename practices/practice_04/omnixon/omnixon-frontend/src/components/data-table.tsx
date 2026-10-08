import { useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type Column,
  type ColumnDef,
  type SortingState,
  type VisibilityState,
} from '@tanstack/react-table'
import {
  ArrowDownIcon,
  ArrowUpDownIcon,
  ArrowUpIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
  Columns3Icon,
  CopyPlusIcon,
  ExternalLinkIcon,
  PencilIcon,
  SearchIcon,
  Trash2Icon,
  XIcon,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ButtonGroup } from '@/components/ui/button-group'
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuGroup, DropdownMenuLabel, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput, InputGroupText } from '@/components/ui/input-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { EmptyState, ErrorBox, LoadingRows } from '@/components/page'
import { fmtDate } from '@/lib/format'
import { cn } from '@/lib/utils'

/** A sortable column header: `header: ({ column }) => <SortHeader column={column} title="Name" />` */
export function SortHeader<T>({ column, title }: { column: Column<T, unknown>; title: string }) {
  const sorted = column.getIsSorted()
  return (
    <Button variant="ghost" size="sm" className="-ml-2 h-7 gap-1 px-2" onClick={() => column.toggleSorting(sorted === 'asc')}>
      {title}
      {sorted === 'asc' ? <ArrowUpIcon /> : sorted === 'desc' ? <ArrowDownIcon /> : <ArrowUpDownIcon className="opacity-50" />}
    </Button>
  )
}

// ---- columns every table shares, so they look and behave the same ----

export function idColumn<T extends { id: number }>(): ColumnDef<T> {
  return {
    accessorKey: 'id',
    meta: { label: 'ID' },
    header: ({ column }) => <SortHeader column={column} title="ID" />,
    cell: ({ getValue }) => <span className="value-mono">{getValue<number>()}</span>,
    size: 72,
  }
}

/** The name of an entity, the first column of every table; `to` makes it a link to the entity. */
export function nameColumn<T extends { id: number; name: string }>(to?: (row: T) => string): ColumnDef<T> {
  return {
    accessorKey: 'name',
    meta: { label: 'Name' },
    header: ({ column }) => <SortHeader column={column} title="Name" />,
    cell: ({ row }) =>
      to ? (
        <Link to={to(row.original)} className="font-medium underline-offset-4 hover:underline" onClick={(e) => e.stopPropagation()}>
          {row.original.name}
        </Link>
      ) : (
        <span className="font-medium">{row.original.name}</span>
      ),
  }
}

export function createdColumn<T extends { timestamp: string }>(label = 'Created'): ColumnDef<T> {
  return {
    accessorKey: 'timestamp',
    meta: { label },
    header: ({ column }) => <SortHeader column={column} title={label} />,
    cell: ({ getValue }) => <span className="whitespace-nowrap text-muted-foreground">{fmtDate(getValue<string>())}</span>,
  }
}

export interface RowAction<T> {
  label: string
  icon: ReactNode
  onClick: (row: T) => void
  disabled?: (row: T) => boolean
  destructive?: boolean
}

/** The same icon and wording for the same action in every table. */
export const rowAction = {
  open: <T,>(onClick: (row: T) => void): RowAction<T> => ({ label: 'Open', icon: <ExternalLinkIcon />, onClick }),
  edit: <T,>(onClick: (row: T) => void, disabled?: (row: T) => boolean): RowAction<T> => ({ label: 'Edit', icon: <PencilIcon />, onClick, disabled }),
  duplicate: <T,>(onClick: (row: T) => void): RowAction<T> => ({ label: 'Duplicate', icon: <CopyPlusIcon />, onClick }),
  remove: <T,>(onClick: (row: T) => void, disabled?: (row: T) => boolean): RowAction<T> => ({
    label: 'Delete',
    icon: <Trash2Icon />,
    destructive: true,
    onClick,
    disabled,
  }),
}

/** A right-aligned column of icon buttons, each with a tooltip and an aria-label. */
export function actionsColumn<T>(actions: RowAction<T>[]): ColumnDef<T> {
  return {
    id: 'actions',
    header: () => <span className="sr-only">Actions</span>,
    enableHiding: false,
    enableSorting: false,
    cell: ({ row }) => (
      <div className="flex justify-end gap-0.5" onClick={(e) => e.stopPropagation()}>
        {actions.map((a) => (
          <Tooltip key={a.label}>
            <TooltipTrigger
              render={
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={a.label}
                  className={a.destructive ? 'text-destructive hover:bg-destructive/10 hover:text-destructive' : undefined}
                  disabled={a.disabled?.(row.original)}
                  onClick={() => a.onClick(row.original)}
                />
              }
            >
              {a.icon}
            </TooltipTrigger>
            <TooltipContent>{a.label}</TooltipContent>
          </Tooltip>
        ))}
      </div>
    ),
  }
}

interface EmptyConfig {
  title: string
  description?: ReactNode
  icon?: React.ComponentType<{ className?: string }>
  action?: ReactNode
}

interface DataTableProps<T> {
  columns: ColumnDef<T>[]
  data: T[] | undefined
  loading?: boolean
  error?: unknown
  onRetry?: () => void
  empty?: EmptyConfig
  searchPlaceholder?: string
  /** Controls next to the column menu (a filter, a count …). */
  toolbar?: ReactNode
  initialSorting?: SortingState
  initialHidden?: VisibilityState
  pageSize?: number
  getRowId?: (row: T) => string
  onRowClick?: (row: T) => void
}

const PAGE_SIZES = [10, 20, 50, 100]

/**
 * The data table of the panel: search, sortable columns, column menu and pagination on
 * TanStack Table. In a flex column that gives it height it fills it: the rows scroll under
 * a sticky header and the pager stays at the bottom.
 */
export function DataTable<T>({
  columns,
  data,
  loading,
  error,
  onRetry,
  empty,
  searchPlaceholder = 'Search…',
  toolbar,
  initialSorting = [],
  initialHidden = {},
  pageSize = 20,
  getRowId,
  onRowClick,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>(initialSorting)
  const [visibility, setVisibility] = useState<VisibilityState>(initialHidden)
  const [filter, setFilter] = useState('')
  const rows = useMemo(() => data ?? [], [data])

  const table = useReactTable({
    data: rows,
    columns,
    getRowId,
    state: { sorting, columnVisibility: visibility, globalFilter: filter },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setVisibility,
    onGlobalFilterChange: setFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
    // search every column that has a plain value
    globalFilterFn: (row, _id, value: string) => {
      const needle = String(value).toLowerCase()
      return row.getAllCells().some((cell) => {
        const v = cell.getValue()
        return v != null && typeof v !== 'object' && String(v).toLowerCase().includes(needle)
      })
    },
  })

  if (error) return <ErrorBox error={error} onRetry={onRetry} />
  if (loading && !data) return <LoadingRows rows={6} className="rounded-xl border p-3" />
  if (!rows.length && empty) return <EmptyState {...empty} className="flex-1" />

  const hideable = table.getAllColumns().filter((c) => c.getCanHide())
  const total = table.getFilteredRowModel().rows.length
  const { pageIndex, pageSize: size } = table.getState().pagination
  const from = total === 0 ? 0 : pageIndex * size + 1
  const to = Math.min(total, (pageIndex + 1) * size)
  const lastIndex = table.getVisibleLeafColumns().length - 1

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <InputGroup className="max-w-xs">
          <InputGroupAddon>
            <SearchIcon />
          </InputGroupAddon>
          <InputGroupInput aria-label="Search the table" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={searchPlaceholder} />
          {filter && (
            <InputGroupAddon align="inline-end">
              <InputGroupButton size="icon-xs" aria-label="Clear the search" onClick={() => setFilter('')}>
                <XIcon />
              </InputGroupButton>
            </InputGroupAddon>
          )}
        </InputGroup>
        <span className="text-sm text-muted-foreground tabular-nums">{filter ? `${total} of ${rows.length}` : rows.length} rows</span>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {toolbar}
          {hideable.length > 1 && (
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}>
                <Columns3Icon /> Columns
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-44">
                <DropdownMenuGroup>
                  <DropdownMenuLabel>Toggle columns</DropdownMenuLabel>
                  {hideable.map((c) => (
                    <DropdownMenuCheckboxItem key={c.id} checked={c.getIsVisible()} onCheckedChange={(v) => c.toggleVisibility(!!v)}>
                      {typeof c.columnDef.meta === 'object' && c.columnDef.meta && 'label' in c.columnDef.meta ? String(c.columnDef.meta.label) : c.id}
                    </DropdownMenuCheckboxItem>
                  ))}
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-xl border bg-card">
        <Table containerClassName="overflow-visible">
          <TableHeader className="sticky top-0 z-10 bg-muted/80 backdrop-blur">
            {table.getHeaderGroups().map((group) => (
              <TableRow key={group.id} className="hover:bg-transparent">
                {group.headers.map((h, i) => (
                  <TableHead
                    key={h.id}
                    className={cn(i === 0 && 'pl-4', i === lastIndex && 'pr-4')}
                    style={h.column.columnDef.size ? { width: h.column.columnDef.size } : undefined}
                  >
                    {h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} className={onRowClick ? 'cursor-pointer' : undefined} onClick={onRowClick ? () => onRowClick(row.original) : undefined}>
                  {row.getVisibleCells().map((cell, i) => (
                    <TableCell key={cell.id} className={cn(i === 0 && 'pl-4', i === lastIndex && 'pr-4')}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={lastIndex + 1} className="h-24 text-center text-muted-foreground">
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
        <span className="tabular-nums">
          {from}–{to} of {total}
        </span>
        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-2 sm:flex">
            Rows per page
            <Select value={String(size)} onValueChange={(v) => v && table.setPageSize(Number(v))} items={PAGE_SIZES.map((n) => ({ value: String(n), label: String(n) }))}>
              <SelectTrigger size="sm" className="w-16" aria-label="Rows per page">
                <SelectValue />
              </SelectTrigger>
              <SelectContent alignItemWithTrigger={false}>
                {PAGE_SIZES.map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <ButtonGroup>
            <Button variant="outline" size="icon-sm" aria-label="First page" disabled={!table.getCanPreviousPage()} onClick={() => table.setPageIndex(0)}>
              <ChevronsLeftIcon />
            </Button>
            <Button variant="outline" size="icon-sm" aria-label="Previous page" disabled={!table.getCanPreviousPage()} onClick={() => table.previousPage()}>
              <ChevronLeftIcon />
            </Button>
            <InputGroupText className="rounded-none border border-x-0 px-3 tabular-nums">
              {pageIndex + 1} / {Math.max(1, table.getPageCount())}
            </InputGroupText>
            <Button variant="outline" size="icon-sm" aria-label="Next page" disabled={!table.getCanNextPage()} onClick={() => table.nextPage()}>
              <ChevronRightIcon />
            </Button>
            <Button variant="outline" size="icon-sm" aria-label="Last page" disabled={!table.getCanNextPage()} onClick={() => table.setPageIndex(table.getPageCount() - 1)}>
              <ChevronsRightIcon />
            </Button>
          </ButtonGroup>
        </div>
      </div>
    </div>
  )
}

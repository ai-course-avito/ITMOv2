import { ApiError, NetworkError } from './client'
import type { Dict } from '../i18n/ru'

// Maps a failed request to a message in the selected language; raw backend text is never shown.
export function messageFor(error: unknown, t: Dict): string {
  if (error instanceof NetworkError) return t.common.errorNetwork
  if (error instanceof ApiError) {
    if (error.status === 401) return t.common.errorSession
    if (error.status === 422) return t.errors.validation
  }
  return t.common.errorGeneric
}

// Pydantic errors look like {loc: ['body', 'amount'], msg, type}; the field is the last string of loc.
export function fieldErrors(error: unknown): Record<string, true> {
  const result: Record<string, true> = {}
  if (!(error instanceof ApiError) || error.status !== 422 || !Array.isArray(error.detail)) {
    return result
  }
  for (const item of error.detail as { loc?: unknown[] }[]) {
    const field = item.loc?.filter((part): part is string => typeof part === 'string').at(-1)
    if (field && field !== 'body') result[camel(field)] = true
  }
  return result
}

const camel = (key: string) => key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())

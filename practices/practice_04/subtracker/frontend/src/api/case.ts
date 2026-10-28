const toCamel = (key: string) => key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
const toSnake = (key: string) => key.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`)

function convertKeys(value: unknown, fn: (key: string) => string): unknown {
  if (Array.isArray(value)) return value.map((item) => convertKeys(item, fn))
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([k, v]) => [fn(k), convertKeys(v, fn)]),
    )
  }
  return value
}

export const camelizeKeys = <T>(value: unknown): T => convertKeys(value, toCamel) as T
export const snakeizeKeys = (value: unknown): unknown => convertKeys(value, toSnake)

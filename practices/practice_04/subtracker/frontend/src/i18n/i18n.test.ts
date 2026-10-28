import { dictionaries } from './index'

function keysOf(value: unknown, prefix = ''): string[] {
  if (typeof value !== 'object' || value === null) return [prefix]
  return Object.entries(value).flatMap(([k, v]) => keysOf(v, prefix ? `${prefix}.${k}` : k))
}

describe('dictionaries', () => {
  it('have exactly the same keys in ru and en', () => {
    expect(keysOf(dictionaries.en).sort()).toEqual(keysOf(dictionaries.ru).sort())
  })

  it('format relative days in both languages', () => {
    expect(dictionaries.ru.subs.when(2)).toBe('Через 2 дня')
    expect(dictionaries.ru.subs.when(25)).toBe('Через 25 дней')
    expect(dictionaries.en.subs.when(1)).toBe('Tomorrow')
    expect(dictionaries.en.subs.when(6)).toBe('In 6 days')
  })
})

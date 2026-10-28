import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { readStored, writeStored } from '../lib/storage'
import { en } from './en'
import { ru, type Dict } from './ru'

export type Lang = 'ru' | 'en'

export const dictionaries: Record<Lang, Dict> = { ru, en }

export const LANG_KEY = 'subtracker.lang'
export const DEFAULT_LANG: Lang = 'ru'

interface I18nValue {
  lang: Lang
  t: Dict
  locale: string
  setLang: (lang: Lang) => void
}

const I18nContext = createContext<I18nValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() =>
    readStored(LANG_KEY) === 'en' ? 'en' : DEFAULT_LANG,
  )

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback((next: Lang) => {
    setLangState(next)
    writeStored(LANG_KEY, next)
  }, [])

  const value = useMemo<I18nValue>(
    () => ({ lang, t: dictionaries[lang], locale: lang === 'ru' ? 'ru-RU' : 'en-US', setLang }),
    [lang, setLang],
  )
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n must be used inside I18nProvider')
  return value
}

export function useT(): Dict {
  return useI18n().t
}

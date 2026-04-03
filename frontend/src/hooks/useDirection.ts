import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

export type Direction = 'ltr' | 'rtl'

const RTL_LANGS = ['he', 'ar']

export function useDirection(): Direction {
  const { i18n } = useTranslation()
  const [dir, setDir] = useState<Direction>(RTL_LANGS.includes(i18n.language) ? 'rtl' : 'ltr')

  useEffect(() => {
    const newDir: Direction = RTL_LANGS.includes(i18n.language) ? 'rtl' : 'ltr'
    setDir(newDir)
    document.documentElement.dir = newDir
    document.documentElement.lang = i18n.language
  }, [i18n.language])

  return dir
}

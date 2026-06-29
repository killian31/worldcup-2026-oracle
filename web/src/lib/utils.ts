import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const flagUrl = (iso: string) => `https://flagcdn.com/${iso}.svg`

export const pct = (x: number | null | undefined, d = 0) =>
  x == null ? '–' : `${(x * 100).toFixed(d)}%`

export const fmtDate = (s: string) =>
  new Date(s + 'T12:00:00Z').toLocaleDateString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric',
  })

const BASE = import.meta.env.BASE_URL
export async function loadJSON<T>(name: string): Promise<T> {
  const res = await fetch(`${BASE}data/${name}.json`, { cache: 'no-cache' })
  if (!res.ok) throw new Error(`failed to load ${name}`)
  return res.json()
}

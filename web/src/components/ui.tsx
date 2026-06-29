import { cn, flagUrl, pct } from '@/lib/utils'
import type { ReactNode } from 'react'

export function Flag({ iso, className }: { iso: string; className?: string }) {
  return (
    <img
      src={flagUrl(iso)} alt="" loading="lazy"
      onError={(e) => ((e.target as HTMLImageElement).style.visibility = 'hidden')}
      className={cn('rounded-[3px] object-cover ring-1 ring-white/10 bg-card2 shrink-0', className)}
    />
  )
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('rounded-xl border border-line bg-card shadow-lg shadow-black/30', className)}>
      {children}
    </div>
  )
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="font-display text-sm font-semibold uppercase tracking-[0.18em] text-muted mt-7 mb-3 first:mt-1">
      {children}
    </h2>
  )
}

export function Badge({ children, tone = 'muted', className }: {
  children: ReactNode; tone?: 'muted' | 'good' | 'bad' | 'brand' | 'upset'; className?: string
}) {
  const tones = {
    muted: 'bg-card2 text-muted border-line',
    good: 'bg-home/15 text-home border-home/30',
    bad: 'bg-upset/15 text-upset border-upset/30',
    brand: 'bg-brand/15 text-brand border-brand/30',
    upset: 'bg-upset/15 text-upset border-upset/40',
  }
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-semibold',
      tones[tone], className)}>
      {children}
    </span>
  )
}

export function Stat({ value, label, tone }: { value: ReactNode; label: string; tone?: 'good' | 'away' | 'brand' }) {
  const c = tone === 'good' ? 'text-home' : tone === 'away' ? 'text-away' : tone === 'brand' ? 'text-brand' : 'text-fg'
  return (
    <Card className="px-4 py-4 text-center">
      <div className={cn('font-display text-3xl font-bold leading-none tnum', c)}>{value}</div>
      <div className="mt-1.5 text-[11px] uppercase tracking-wide text-muted">{label}</div>
    </Card>
  )
}

/** 3-segment win/draw/win probability bar */
export function ProbBar({ probs, t1, t2 }: { probs: [number, number, number]; t1: string; t2: string }) {
  const [h, d, a] = probs
  const seg = (w: number, cls: string, label: string, title: string) =>
    w < 0.001 ? null : (
      <div className={cn('flex items-center justify-center text-[11px] font-bold text-black/85 tnum transition-all', cls)}
        style={{ width: `${w * 100}%` }} title={title}>
        {w >= 0.12 ? label : ''}
      </div>
    )
  return (
    <div className="mt-3 flex h-7 overflow-hidden rounded-lg border border-line">
      {seg(h, 'bg-home', pct(h), `${t1} win`)}
      {seg(d, 'bg-draw text-black/80', `X ${pct(d)}`, 'Draw')}
      {seg(a, 'bg-away', pct(a), `${t2} win`)}
    </div>
  )
}

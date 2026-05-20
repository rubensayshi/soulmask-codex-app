import { useState } from 'react'
import type { Tribesman, TraitMatch, SortState, BadgeShape, Tier } from '../lib/types'
import { ClanTag, GroupTag } from '../components/Parts'
import { PROF_SKILLS } from '../lib/data'
import { TraitBadge, TraitBadgeLg, SHAPE_COLORS, TIER_COLORS } from '../components/TraitBadge'
import { IcoChevRight } from '../components/Icons'
import { useEffectiveTier, useTierStore } from '../lib/tierStore'

interface Props {
  rows: Tribesman[]
  sort: SortState
  setSort: (s: SortState) => void
  showProf: boolean
}

export function RosterTable({ rows, sort, setSort, showProf }: Props) {
  const [expanded, setExpanded] = useState<string | null>(rows[0]?.id ?? null)

  return (
    <div style={{ padding: '0 22px 22px' }}>
      <table className="w-full" style={{ borderCollapse: 'separate', borderSpacing: 0, fontSize: '12.5px' }}>
        <thead>
          <tr>
            <Th width={24} />
            <SortTh k="name" label="Name" sort={sort} setSort={setSort} />
            <SortTh k="level" label="Lv." sort={sort} setSort={setSort} width={72} />
            <SortTh k="klass" label="Class" sort={sort} setSort={setSort} width={160} />
            <SortTh k="clan" label="Clan" sort={sort} setSort={setSort} width={100} />
            <SortTh k="title" label="Title" sort={sort} setSort={setSort} width={170} />
            <Th width="34%">Traits</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map(tm => {
            const open = expanded === tm.id
            return (
              <Row key={tm.id} tm={tm} open={open} showProf={showProf}
                onClick={() => setExpanded(open ? null : tm.id)} />
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function Th({ children, width }: { children?: React.ReactNode; width?: number | string }) {
  return (
    <th
      className="text-left select-none whitespace-nowrap sticky top-0"
      style={{
        background: 'var(--color-bg)',
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        fontWeight: 500,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color: 'var(--color-muted)',
        padding: '14px 12px 10px',
        borderBottom: '1px solid var(--color-border)',
        width,
      }}
    >
      {children}
    </th>
  )
}

function SortTh({ k, label, sort, setSort, width }: {
  k: string; label: string; sort: SortState; setSort: (s: SortState) => void; width?: number
}) {
  const active = sort.key === k
  const onClick = () => setSort({ key: k, dir: active && sort.dir === 'asc' ? 'desc' : 'asc' })
  return (
    <th
      className="text-left cursor-default select-none whitespace-nowrap sticky top-0 hover:!text-[var(--color-text)]"
      style={{
        background: 'var(--color-bg)',
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        fontWeight: 500,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color: 'var(--color-muted)',
        padding: '14px 12px 10px',
        borderBottom: '1px solid var(--color-border)',
        width,
      }}
      onClick={onClick}
    >
      {label}
      <span style={{ marginLeft: 4, fontSize: 9, color: 'var(--color-accent)', opacity: active ? 1 : 0 }}>
        {active ? (sort.dir === 'asc' ? '▲' : '▼') : '▲'}
      </span>
    </th>
  )
}

function Row({ tm, open, showProf, onClick }: { tm: Tribesman; open: boolean; showProf: boolean; onClick: () => void }) {
  const rowBg = open
    ? 'oklch(0.22 0.012 140 / 0.45)'
    : undefined
  const hoverBg = 'oklch(0.20 0.008 130 / 0.6)'

  return (
    <>
      <tr
        className="cursor-default group"
        style={{ background: rowBg, transition: 'background 0.1s' }}
        onClick={onClick}
        onMouseEnter={e => { if (!open) (e.currentTarget as HTMLElement).style.background = hoverBg }}
        onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = rowBg || '' }}
      >
        <td style={{ ...tdStyle, borderBottom: open ? 'none' : undefined }}>
          <span
            className="inline-flex transition-transform duration-150"
            style={{ color: open ? 'var(--color-accent)' : 'var(--color-muted)', transform: open ? 'rotate(90deg)' : undefined }}
          >
            <IcoChevRight />
          </span>
        </td>
        <td style={{ ...tdStyle, borderBottom: open ? 'none' : undefined }}>
          <div style={{ fontFamily: 'var(--font-serif)', fontSize: 16, fontWeight: 500, letterSpacing: '0.005em' }}>
            {tm.name}
          </div>
          <div className="flex items-center gap-2 whitespace-nowrap" style={{ marginTop: 1 }}>
            <GroupTag group={tm.group} />
            <span style={{ fontSize: 10.5, color: 'var(--color-muted)' }}>· {tm.location}</span>
          </div>
        </td>
        <td style={{ ...tdStyle, borderBottom: open ? 'none' : undefined }}>
          <span className="cell-level" style={{ fontFamily: 'var(--font-serif)', fontSize: 17, color: 'var(--color-accent)', fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>
            {tm.level}
          </span>
        </td>
        <td style={{ ...tdStyle, color: 'var(--color-text-dim)', fontSize: '12.5px', borderBottom: open ? 'none' : undefined }}>
          {stripClassPrefix(tm.klass)}
        </td>
        <td style={{ ...tdStyle, borderBottom: open ? 'none' : undefined }}>
          <ClanTag clan={tm.clan} />
        </td>
        <td style={{ ...tdStyle, borderBottom: open ? 'none' : undefined }}>
          <span style={{ fontFamily: 'var(--font-serif)', fontStyle: 'italic', color: tm.title === '—' ? 'var(--color-faint)' : 'var(--color-gold)', fontSize: 14 }}>
            {tm.title}
          </span>
        </td>
        <td style={{ ...tdStyle, borderBottom: open ? 'none' : undefined }}>
          <div className="flex items-center gap-1">
            {tm.traits.map(t => (
              <TraitBadge key={t.id} trait={t} />
            ))}
          </div>
        </td>
      </tr>
      {open && (
        <tr style={{ background: 'oklch(0.18 0.010 140 / 0.4)' }}>
          <td colSpan={7} style={{ padding: 0, borderBottom: '1px solid var(--color-border)', height: 'auto' }}>
            <ExpandedRow tm={tm} showProf={showProf} />
          </td>
        </tr>
      )}
    </>
  )
}

const tdStyle: React.CSSProperties = {
  padding: '0 12px',
  borderBottom: '1px solid var(--color-border-soft)',
  verticalAlign: 'middle',
  height: 48,
}

export function ExpandedRow({ tm, showProf }: { tm: Tribesman; showProf: boolean }) {
  const byShape: Record<BadgeShape, typeof tm.traits> = {
    hexagon: tm.traits.filter(t => t.shape === 'hexagon'),
    shield: tm.traits.filter(t => t.shape === 'shield'),
    diamond: tm.traits.filter(t => t.shape === 'diamond'),
  }

  return (
    <div className="grid grid-cols-2" style={{ padding: '18px 22px 22px', borderTop: '1px solid var(--color-accent-soft)' }}>
      <div style={{ padding: '0 16px' }}>
        <h3 style={{ margin: '0 0 14px', fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.14em', color: 'var(--color-accent)', textTransform: 'uppercase', fontWeight: 500 }}>
          ◆ Details
        </h3>
        <dl className="grid gap-x-4 gap-y-1.5" style={{ gridTemplateColumns: 'max-content 1fr', fontSize: 12, marginBottom: 16 }}>
          <Dt>Class</Dt><Dd>{stripClassPrefix(tm.klass)}</Dd>
          <Dt>Title</Dt><Dd><em style={{ fontFamily: 'var(--font-serif)', fontStyle: 'italic', color: 'var(--color-gold)' }}>{tm.title}</em></Dd>
          <Dt>Group</Dt><Dd><GroupTag group={tm.group} /></Dd>
          <Dt>Location</Dt><Dd>{tm.location}</Dd>
          <Dt>Clan</Dt><Dd><ClanTag clan={tm.clan} /></Dd>
        </dl>

        {showProf && (
          <>
            <h3 style={{ margin: '0 0 14px', fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.14em', color: 'var(--color-accent)', textTransform: 'uppercase', fontWeight: 500 }}>
              ◆ Proficiencies
            </h3>
            <div className="grid grid-cols-4 gap-x-3.5 gap-y-1.5" style={{ fontSize: 11, color: 'var(--color-text-dim)' }}>
              {PROF_SKILLS.map((s, i) => (
                <div key={s} className="flex items-center justify-between gap-1.5">
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, letterSpacing: '0.06em', color: 'var(--color-muted)', textTransform: 'uppercase' }}>{s}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: (tm.prof[i] || 0) >= 120 ? 'oklch(0.65 0.2 25)' : (tm.prof[i] || 0) >= 90 ? 'oklch(0.75 0.15 70)' : 'var(--color-text-dim)', fontVariantNumeric: 'tabular-nums' }}>
                    {tm.prof[i] || 0}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <div style={{ padding: '0 16px', borderLeft: '1px solid var(--color-border-soft)' }}>
        <h3 style={{ margin: '0 0 14px', fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.14em', color: 'var(--color-accent)', textTransform: 'uppercase', fontWeight: 500 }}>
          ◆ Traits · {tm.traits.length}
        </h3>
        {byShape.hexagon.map(t => <TraitDetailItem key={t.id} trait={t} />)}
        {byShape.shield.map(t => <TraitDetailItem key={t.id} trait={t} />)}
        {byShape.diamond.map(t => <TraitDetailItem key={t.id} trait={t} />)}
      </div>
    </div>
  )
}

function Dt({ children }: { children: React.ReactNode }) {
  return (
    <dt style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, color: 'var(--color-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', alignSelf: 'center' }}>
      {children}
    </dt>
  )
}

function Dd({ children }: { children: React.ReactNode }) {
  return <dd style={{ margin: 0, color: 'var(--color-text)', alignSelf: 'center' }}>{children}</dd>
}

const ALL_TIERS: (Tier | null)[] = ['S', 'A', 'B', 'C', 'D', 'F', null]

function TraitDetailItem({ trait }: { trait: TraitMatch }) {
  const c = SHAPE_COLORS[trait.shape]
  const tier = useEffectiveTier(trait.icon_name, trait.tier)
  const setTier = useTierStore(s => s.setTier)
  const removeTier = useTierStore(s => s.removeTier)
  const [popoverOpen, setPopoverOpen] = useState(false)
  const tc = tier ? TIER_COLORS[tier] : null
  const sourceLabel = trait.shape === 'hexagon' ? 'Learned · Talent'
    : trait.shape === 'diamond' ? 'Preference'
    : 'Innate · Tribe-born'

  const pickTier = (t: Tier | null) => {
    if (t) setTier(trait.icon_name, t)
    else removeTier(trait.icon_name)
    setPopoverOpen(false)
  }

  return (
    <div className="flex gap-3 items-start" style={{ padding: '10px 0', borderBottom: '1px solid var(--color-border-soft)' }}>
      <TraitBadgeLg trait={trait} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2" style={{ fontFamily: 'var(--font-serif)', fontSize: 14, color: 'var(--color-text)' }}>
          {trait.name}
          <span style={{ color: 'var(--color-gold)', fontSize: 11 }}>
            {'★'.repeat(trait.star)}
          </span>
          <span className="relative">
            <button
              onClick={(e) => { e.stopPropagation(); setPopoverOpen(!popoverOpen) }}
              title="Click to change tier"
              style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                padding: '0 5px', height: 16, borderRadius: 3,
                background: tc?.bg ?? 'var(--color-border)',
                color: tc?.text ?? 'var(--color-muted)',
                fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
                letterSpacing: '0.04em',
                cursor: 'pointer',
                opacity: tc ? 1 : 0.5,
              }}
            >
              {tier ?? '—'}
            </button>
            {popoverOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setPopoverOpen(false)} />
                <div
                  className="absolute z-50 flex gap-0.5 rounded-[var(--radius)] border border-border-soft"
                  style={{
                    top: '100%', left: '50%', transform: 'translateX(-50%)',
                    marginTop: 4, padding: 3,
                    background: 'var(--color-bg-elev)',
                    boxShadow: '0 8px 24px oklch(0 0 0 / 0.5)',
                  }}
                >
                  {ALL_TIERS.map(t => {
                    const colors = t ? TIER_COLORS[t] : null
                    const active = t === tier
                    return (
                      <button
                        key={t ?? 'none'}
                        onClick={(e) => { e.stopPropagation(); pickTier(t) }}
                        style={{
                          width: 22, height: 22, borderRadius: 3,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          background: active ? (colors?.bg ?? 'var(--color-border)') : 'transparent',
                          color: active ? (colors?.text ?? 'var(--color-muted)') : (colors?.bg ?? 'var(--color-muted)'),
                          fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                          cursor: 'pointer',
                          border: active ? '1px solid oklch(1 0 0 / 0.15)' : '1px solid transparent',
                        }}
                      >
                        {t ?? '—'}
                      </button>
                    )
                  })}
                </div>
              </>
            )}
          </span>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, color: c.stroke, letterSpacing: '0.06em', textTransform: 'uppercase', marginTop: 2 }}>
          {sourceLabel}
          {trait.tier_tags?.length ? (
            <span style={{ color: 'var(--color-muted)', marginLeft: 8 }}>
              {trait.tier_tags.join(' · ')}
            </span>
          ) : null}
        </div>
        <div style={{ fontSize: 11.5, color: 'var(--color-text-dim)', marginTop: 4 }}>
          {trait.eff}
        </div>
        {trait.tier_note && (
          <div style={{ fontSize: 10.5, color: 'var(--color-muted)', marginTop: 3, fontStyle: 'italic' }}>
            {trait.tier_note}
          </div>
        )}
      </div>
    </div>
  )
}

function stripClassPrefix(klass: string): string {
  return klass.replace(/^(Skilled|Novice|Master)\s+/, '')
}

export function sortRows(rows: Tribesman[], sort: SortState): Tribesman[] {
  const { key, dir } = sort
  const mult = dir === 'asc' ? 1 : -1
  return rows.slice().sort((a, b) => {
    const va = (a as unknown as Record<string, unknown>)[key]
    const vb = (b as unknown as Record<string, unknown>)[key]
    if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * mult
    return String(va ?? '').localeCompare(String(vb ?? '')) * mult
  })
}

const TIER_ORDER: Record<string, number> = { S: 0, A: 1, B: 2, C: 3, D: 4, F: 5 }

export function filterRows(rows: Tribesman[], filters: { clan: string; groups: string[]; traits: string[]; minLevel: number | null; minTier: string | null; prof: { skill: number; min: number } | null }, query: string): Tribesman[] {
  return rows.filter(r => {
    if (filters.clan !== 'all' && r.clan !== filters.clan) return false
    if (filters.groups.length > 0 && !filters.groups.includes(r.group)) return false
    if (filters.minLevel !== null && r.level < filters.minLevel) return false
    if (filters.traits.length > 0) {
      const traitIds = new Set(r.traits.map(t => t.id))
      if (!filters.traits.every(id => traitIds.has(id))) return false
    }
    if (filters.minTier !== null) {
      const threshold = TIER_ORDER[filters.minTier] ?? 99
      if (!r.traits.some(t => t.tier && (TIER_ORDER[t.tier] ?? 99) <= threshold)) return false
    }
    if (filters.prof !== null && (r.prof[filters.prof.skill] ?? 0) < filters.prof.min) return false
    if (query) {
      const q = query.toLowerCase()
      const hay = (r.name + ' ' + r.title + ' ' + r.klass + ' ' + r.clan + ' ' + (r.group || '')).toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
}

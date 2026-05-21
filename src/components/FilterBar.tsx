import { useState, useMemo } from 'react'
import { CLANS, PROF_SKILLS, ENABLE_PROFICIENCIES } from '../lib/data'
import { TIER_COLORS } from './TraitBadge'
import { getBestTrait } from '../lib/traits'
import type { Filters, ClanName, Tribesman, Tier, BadgeShape } from '../lib/types'

const CLAN_LIST: ClanName[] = ['Claw', 'Flint', 'Fang', 'Wolf', 'Horn', 'Exile', 'DLC']
const TIER_LIST: Tier[] = ['S', 'A', 'B', 'C']
const TIER_ORDER: Record<string, number> = { S: 0, A: 1, B: 2, C: 3, D: 4, F: 5 }

interface Props {
  filters: Filters
  setFilters: (f: Filters) => void
  roster: Tribesman[]
}

const ALL_SHAPES: BadgeShape[] = ['hexagon', 'diamond', 'shield']

const SHAPE_PATHS: Record<BadgeShape, string> = {
  hexagon: 'M6,0.75 L11,3.25 L11,8.75 L6,11.25 L1,8.75 L1,3.25 Z',
  diamond: 'M6,0.75 L11.25,6 L6,11.25 L0.75,6 Z',
  shield:  'M6,1 L10.5,3.5 L10.5,7 Q10.5,10 6,11.5 Q1.5,10 1.5,7 L1.5,3.5 Z',
}

const SHAPE_LABELS: Record<BadgeShape, string> = {
  hexagon: 'Learned',
  diamond: 'Preference',
  shield:  'Innate',
}

export function FilterBar({ filters, setFilters, roster }: Props) {
  const [tierFilter, setTierFilter] = useState<Tier | null>(null)
  const [shapeFilter, setShapeFilter] = useState<Set<BadgeShape>>(new Set<BadgeShape>(['hexagon', 'shield']))
  const [polarityFilter, setPolarityFilter] = useState<'positive' | 'negative' | 'all'>('positive')

  const allGroups = useMemo(() => {
    const seen = new Set<string>()
    for (const tm of roster) {
      if (tm.group) seen.add(tm.group)
    }
    return Array.from(seen).sort((a, b) => a.localeCompare(b))
  }, [roster])

  const allTraits = useMemo(() => {
    const seen = new Map<string, { name: string; tier: Tier | null; shape: BadgeShape; is_negative: boolean }>()
    for (const tm of roster) {
      for (const t of tm.traits) {
        const existing = seen.get(t.id)
        if (!existing) {
          const info = getBestTrait(t.icon_name)
          seen.set(t.id, {
            name: t.name,
            tier: (t.tier as Tier) ?? null,
            shape: t.shape,
            is_negative: info?.is_negative ?? false,
          })
        } else if (t.tier && (!existing.tier || (TIER_ORDER[t.tier] ?? 99) < (TIER_ORDER[existing.tier] ?? 99))) {
          existing.tier = t.tier as Tier
        }
      }
    }
    return Array.from(seen.entries())
      .map(([id, info]) => ({ id, ...info }))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [roster])

  const visibleTraits = useMemo(() => {
    return allTraits.filter(t => {
      if (tierFilter) {
        const threshold = TIER_ORDER[tierFilter] ?? 99
        const effective = TIER_ORDER[t.tier ?? 'C'] ?? 3
        if (effective > threshold) return false
      }
      if (!shapeFilter.has(t.shape)) return false
      if (polarityFilter === 'positive' && t.is_negative) return false
      if (polarityFilter === 'negative' && !t.is_negative) return false
      return true
    })
  }, [allTraits, tierFilter, shapeFilter, polarityFilter])

  function toggleGroup(id: string) {
    const cur = filters.groups
    const next = cur.includes(id) ? cur.filter(g => g !== id) : [...cur, id]
    setFilters({ ...filters, groups: next })
  }

  function toggleTrait(id: string) {
    const cur = filters.traits
    const next = cur.includes(id) ? cur.filter(t => t !== id) : [...cur, id]
    setFilters({ ...filters, traits: next })
  }

  function toggleShape(s: BadgeShape) {
    const next = new Set(shapeFilter)
    if (next.has(s)) next.delete(s); else next.add(s)
    if (next.size === 0) return
    setShapeFilter(next)
  }

  const allGroupsActive = filters.groups.length === 0

  return (
    <div
      className="flex items-center gap-2 flex-wrap border-b border-border-soft"
      style={{ padding: '14px 22px', background: 'oklch(0.155 0.006 130)' }}
    >
      {/* Clan */}
      <span className="uppercase" style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', letterSpacing: '0.1em', marginRight: 4 }}>
        Clan
      </span>
      <Chip on={filters.clan === 'all'} onClick={() => setFilters({ ...filters, clan: 'all' })}>
        All
      </Chip>
      {CLAN_LIST.map(c => {
        const hue = CLANS[c].hue
        const on = filters.clan === c
        return (
          <Chip key={c} on={on} onClick={() => setFilters({ ...filters, clan: c })}
            style={on ? { color: hue, borderColor: hue } : {}}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: hue }} />
            {c}
          </Chip>
        )
      })}

      <span style={{ width: 14 }} />

      {/* Level */}
      <span className="uppercase" style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', letterSpacing: '0.1em', marginRight: 4 }}>
        Level
      </span>
      <Chip on={filters.minLevel === null} onClick={() => setFilters({ ...filters, minLevel: null })}>
        Any
      </Chip>
      {[30, 40, 50].map(lv => (
        <Chip key={lv} on={filters.minLevel === lv} onClick={() => setFilters({ ...filters, minLevel: lv })}>
          {lv}+
        </Chip>
      ))}
      <div
        className="inline-flex items-center gap-1 rounded-full border transition-all duration-100"
        style={{
          height: 28,
          padding: '0 8px',
          border: `1px solid ${filters.minLevel !== null && ![30, 40, 50].includes(filters.minLevel) ? 'var(--color-accent-soft)' : 'var(--color-border)'}`,
          background: filters.minLevel !== null && ![30, 40, 50].includes(filters.minLevel) ? 'var(--color-accent-glow)' : 'transparent',
        }}
      >
        <input
          type="number"
          min={1}
          max={99}
          placeholder="Min"
          className="bg-transparent border-0 outline-0 w-8 text-center"
          style={{
            fontSize: 11,
            color: 'var(--color-text-dim)',
            fontFamily: 'var(--font-mono)',
          }}
          value={filters.minLevel !== null && ![30, 40, 50].includes(filters.minLevel) ? filters.minLevel : ''}
          onChange={e => {
            const v = e.target.value ? parseInt(e.target.value, 10) : null
            setFilters({ ...filters, minLevel: v && v > 0 ? v : null })
          }}
        />
        <span style={{ fontSize: 10, color: 'var(--color-muted)' }}>+</span>
      </div>

      <span style={{ flexBasis: '100%', height: 0 }} />

      {/* Group */}
      <span className="uppercase" style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', letterSpacing: '0.1em', marginRight: 4 }}>
        Group
      </span>
      <Chip on={allGroupsActive} onClick={() => setFilters({ ...filters, groups: [] })}>
        All
      </Chip>
      {allGroups.map(g => {
        const on = filters.groups.includes(g)
        return (
          <Chip key={g} on={on} onClick={() => toggleGroup(g)}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2, color: on ? 'var(--color-accent)' : 'var(--color-muted)' }}>
              <svg width={8} height={8} viewBox="0 0 10 10">
                <circle cx="2" cy="2" r="1.2" fill="currentColor" />
                <circle cx="5" cy="2" r="1.2" fill="currentColor" />
                <circle cx="8" cy="2" r="1.2" fill="currentColor" />
                <circle cx="2" cy="5" r="1.2" fill="currentColor" />
                <circle cx="5" cy="5" r="1.2" fill="currentColor" />
                <circle cx="8" cy="5" r="1.2" fill="currentColor" />
              </svg>
            </span>
            {g}
          </Chip>
        )
      })}

      <span style={{ flexBasis: '100%', height: 0 }} />

      {/* Traits + tier filter */}
      <span className="uppercase" style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', letterSpacing: '0.1em', marginRight: 4 }}>
        Traits
      </span>
      <Chip on={filters.traits.length === 0 && tierFilter === null && shapeFilter.size === 2 && shapeFilter.has('hexagon') && shapeFilter.has('shield') && polarityFilter === 'positive'} onClick={() => { setFilters({ ...filters, traits: [] }); setTierFilter(null); setShapeFilter(new Set<BadgeShape>(['hexagon', 'shield'])); setPolarityFilter('positive') }}>
        Any
      </Chip>

      <span className="inline-flex items-center" style={{ gap: 2, marginRight: 6 }}>
        {TIER_LIST.map(tier => {
          const on = tierFilter === tier
          const tc = TIER_COLORS[tier]
          return (
            <button
              key={tier}
              onClick={() => setTierFilter(on ? null : tier)}
              className="transition-all duration-100"
              style={{
                width: 28, height: 26,
                borderRadius: 4,
                border: `1.5px solid ${on ? tc.bg : 'transparent'}`,
                background: on ? tc.bg : `color-mix(in oklch, ${tc.bg} 20%, transparent)`,
                color: on ? tc.text : tc.bg,
                fontSize: 10,
                fontWeight: 700,
                fontFamily: 'var(--font-mono)',
                lineHeight: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                opacity: on ? 1 : 0.7,
              }}
            >
              {tier}
            </button>
          )
        })}
      </span>

      <span className="inline-flex items-center" style={{ gap: 2, marginRight: 6 }}>
        {ALL_SHAPES.map(s => {
          const on = shapeFilter.has(s)
          return (
            <button
              key={s}
              onClick={() => toggleShape(s)}
              title={SHAPE_LABELS[s]}
              className="transition-all duration-100"
              style={{
                width: 28, height: 26,
                borderRadius: 4,
                border: `1.5px solid ${on ? 'var(--color-accent-soft)' : 'transparent'}`,
                background: on ? 'var(--color-accent-glow)' : 'color-mix(in oklch, var(--color-accent-soft) 15%, transparent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                opacity: on ? 1 : 0.4,
              }}
            >
              <svg width={12} height={12} viewBox="0 0 12 12">
                <path d={SHAPE_PATHS[s]} fill={on ? 'var(--color-accent)' : 'var(--color-muted)'} stroke="none" />
              </svg>
            </button>
          )
        })}
      </span>

      <span className="inline-flex items-center" style={{ gap: 2 }}>
        {(['positive', 'negative', 'all'] as const).map(p => {
          const on = polarityFilter === p
          const label = p === 'positive' ? '+' : p === 'negative' ? '−' : '±'
          return (
            <button
              key={p}
              onClick={() => setPolarityFilter(p)}
              title={p.charAt(0).toUpperCase() + p.slice(1)}
              className="transition-all duration-100"
              style={{
                width: 28, height: 26,
                borderRadius: 4,
                border: `1.5px solid ${on ? 'var(--color-accent-soft)' : 'transparent'}`,
                background: on ? 'var(--color-accent-glow)' : 'color-mix(in oklch, var(--color-accent-soft) 15%, transparent)',
                color: on ? 'var(--color-accent)' : 'var(--color-muted)',
                fontSize: 13,
                fontWeight: 700,
                fontFamily: 'var(--font-mono)',
                lineHeight: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                opacity: on ? 1 : 0.5,
              }}
            >
              {label}
            </button>
          )
        })}
      </span>

      {visibleTraits.map(({ id, name, tier }) => {
        const on = filters.traits.includes(id)
        const effectiveTier = tier ?? 'C' as Tier
        const tc = TIER_COLORS[effectiveTier]
        return (
          <Chip key={id} on={on} onClick={() => toggleTrait(id)}>
            {name}
            <span style={{
              fontSize: 8,
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              lineHeight: 1,
              padding: '1px 3px',
              borderRadius: 3,
              background: tc.bg,
              color: tc.text,
              marginLeft: 2,
            }}>
              {effectiveTier}
            </span>
          </Chip>
        )
      })}
      {filters.traits.length > 0 && (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, color: 'var(--color-muted)', letterSpacing: '0.06em', marginLeft: 4 }}>
          · {filters.traits.length} selected (AND)
        </span>
      )}

      {ENABLE_PROFICIENCIES && <>
      <span style={{ flexBasis: '100%', height: 0 }} />

      {/* Proficiency */}
      <span className="uppercase" style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', letterSpacing: '0.1em', marginRight: 4 }}>
        Prof.
      </span>
      <Chip on={filters.prof === null} onClick={() => setFilters({ ...filters, prof: null })}>
        Any
      </Chip>
      {PROF_SKILLS.map((skill, idx) => {
        const on = filters.prof !== null && filters.prof.skill === idx
        return (
          <Chip key={skill} on={on} onClick={() => setFilters({ ...filters, prof: on ? null : { skill: idx, min: filters.prof?.min ?? 90 } })}>
            {skill}
          </Chip>
        )
      })}
      {filters.prof !== null && (
        <>
          <span style={{ width: 8 }} />
          <span className="uppercase" style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', letterSpacing: '0.1em' }}>
            min
          </span>
          {[90, 120, 150].map(v => (
            <Chip key={v} on={filters.prof !== null && filters.prof.min === v}
              onClick={() => setFilters({ ...filters, prof: { skill: filters.prof!.skill, min: v } })}>
              {v}+
            </Chip>
          ))}
          <div
            className="inline-flex items-center gap-1 rounded-full border transition-all duration-100"
            style={{
              height: 28,
              padding: '0 8px',
              border: `1px solid ${filters.prof !== null && ![90, 120, 150].includes(filters.prof.min) ? 'var(--color-accent-soft)' : 'var(--color-border)'}`,
              background: filters.prof !== null && ![90, 120, 150].includes(filters.prof.min) ? 'var(--color-accent-glow)' : 'transparent',
            }}
          >
            <input
              type="number"
              min={1}
              max={200}
              placeholder="Min"
              className="bg-transparent border-0 outline-0 w-8 text-center"
              style={{ fontSize: 11, color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}
              value={![90, 120, 150].includes(filters.prof.min) ? filters.prof.min : ''}
              onChange={e => {
                const v = e.target.value ? parseInt(e.target.value, 10) : 90
                setFilters({ ...filters, prof: { skill: filters.prof!.skill, min: Math.max(1, v) } })
              }}
            />
            <span style={{ fontSize: 10, color: 'var(--color-muted)' }}>+</span>
          </div>
        </>
      )}
      </>}
    </div>
  )
}

function Chip({ on, onClick, children, style, title }: {
  on: boolean
  onClick: () => void
  children: React.ReactNode
  style?: React.CSSProperties
  title?: string
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="inline-flex items-center gap-1.5 rounded-full border transition-all duration-100"
      style={{
        height: 28,
        padding: '0 10px',
        fontSize: '11.5px',
        border: `1px solid ${on ? 'var(--color-accent-soft)' : 'var(--color-border)'}`,
        background: on ? 'var(--color-accent-glow)' : 'transparent',
        color: on ? 'var(--color-accent)' : 'var(--color-text-dim)',
        ...style,
      }}
    >
      {children}
    </button>
  )
}

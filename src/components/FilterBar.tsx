import { useState, useMemo } from 'react'
import { CLANS, PROF_SKILLS, ENABLE_PROFICIENCIES } from '../lib/data'
import { TIER_COLORS } from './TraitBadge'
import type { Filters, ClanName, Tribesman, Tier } from '../lib/types'

const CLAN_LIST: ClanName[] = ['Claw', 'Flint', 'Fang', 'Wolf', 'Horn', 'Exile', 'DLC']
const TIER_LIST: Tier[] = ['S', 'A', 'B', 'C']
const TIER_ORDER: Record<string, number> = { S: 0, A: 1, B: 2, C: 3, D: 4, F: 5 }

interface Props {
  filters: Filters
  setFilters: (f: Filters) => void
  roster: Tribesman[]
}

export function FilterBar({ filters, setFilters, roster }: Props) {
  const [tierFilter, setTierFilter] = useState<Tier | null>(null)

  const allGroups = useMemo(() => {
    const seen = new Set<string>()
    for (const tm of roster) {
      if (tm.group) seen.add(tm.group)
    }
    return Array.from(seen).sort((a, b) => a.localeCompare(b))
  }, [roster])

  const allTraits = useMemo(() => {
    const seen = new Map<string, { name: string; tier: Tier | null }>()
    for (const tm of roster) {
      for (const t of tm.traits) {
        const existing = seen.get(t.id)
        if (!existing) {
          seen.set(t.id, { name: t.name, tier: (t.tier as Tier) ?? null })
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
    if (!tierFilter) return allTraits
    const threshold = TIER_ORDER[tierFilter] ?? 99
    return allTraits.filter(t => t.tier && (TIER_ORDER[t.tier] ?? 99) <= threshold)
  }, [allTraits, tierFilter])

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
          height: 26,
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
      <Chip on={filters.traits.length === 0 && tierFilter === null} onClick={() => { setFilters({ ...filters, traits: [] }); setTierFilter(null) }}>
        Any
      </Chip>

      {TIER_LIST.map(tier => {
        const on = tierFilter === tier
        const tc = TIER_COLORS[tier]
        return (
          <Chip key={tier} on={on} onClick={() => setTierFilter(on ? null : tier)}
            style={on ? { color: tc.text, borderColor: tc.bg, background: tc.bg } : {}}>
            {tier}+
          </Chip>
        )
      })}

      <span style={{ width: 1, height: 16, background: 'var(--color-border)', margin: '0 4px' }} />

      {visibleTraits.map(({ id, name, tier }) => {
        const on = filters.traits.includes(id)
        const tc = tier ? TIER_COLORS[tier] : null
        return (
          <Chip key={id} on={on} onClick={() => toggleTrait(id)}>
            {name}
            {tc && (
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
                {tier}
              </span>
            )}
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
              height: 26,
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
        height: 26,
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

import type { TraitInfo, Tier } from './types'
import traitsData from '../../assets/traits.json'
import rankingsData from '../../assets/trait_rankings.json'

const traitsArray = traitsData as TraitInfo[]

const byIconName = new Map<string, TraitInfo[]>()
for (const t of traitsArray) {
  if (!t.icon_name) continue
  const arr = byIconName.get(t.icon_name) || []
  arr.push(t)
  byIconName.set(t.icon_name, arr)
}

export function getTraitsByIconName(iconName: string): TraitInfo[] {
  return byIconName.get(iconName) || []
}

export function getBestTrait(iconName: string): TraitInfo | null {
  const traits = getTraitsByIconName(iconName)
  if (!traits.length) return null
  return traits.reduce((a, b) => (b.star > a.star ? b : a))
}

export { traitsArray }

export const clanExclusiveIds: Map<string, string> = new Map()
for (const t of traitsArray) {
  if (t.clan && t.source === 'Normal') {
    clanExclusiveIds.set(t.id, t.clan.toLowerCase())
  }
}

// ── Tier rankings lookup ──

interface RankingEntry { tier: string; tags: string[]; note: string }

const entries = (rankingsData as { entries: Record<string, RankingEntry> }).entries

const tierByLearnedId = new Map<string, RankingEntry>()
const tierByNameZh = new Map<string, RankingEntry>()
const tierByNameEn = new Map<string, RankingEntry>()

for (const [key, entry] of Object.entries(entries)) {
  if (key.startsWith('name_zh:')) {
    tierByNameZh.set(key.slice(8), entry)
  } else if (key.startsWith('name:')) {
    tierByNameEn.set(key.slice(5), entry)
  } else {
    tierByLearnedId.set(key, entry)
  }
}

const tierByIconName = new Map<string, RankingEntry>()
for (const t of traitsArray) {
  if (!t.icon_name || tierByIconName.has(t.icon_name)) continue
  const allForIcon = byIconName.get(t.icon_name) || [t]
  for (const v of allForIcon) {
    const raw = v as TraitInfo & { learned_id?: string | null }
    const lid = raw.learned_id ?? v.id
    const entry =
      (lid && tierByLearnedId.get(lid)) ||
      (v.id && tierByLearnedId.get(v.id)) ||
      (v.name_zh && tierByNameZh.get(v.name_zh)) ||
      null
    if (entry) { tierByIconName.set(t.icon_name, entry); break }
  }
}

export interface TierInfo {
  tier: Tier
  tags: string[]
  note: string
}

export function getTierForIcon(iconName: string): TierInfo | null {
  const entry = tierByIconName.get(iconName)
  if (!entry) return null
  return { tier: entry.tier as Tier, tags: entry.tags, note: entry.note }
}

export function getTierForName(name: string): TierInfo | null {
  const entry = tierByNameEn.get(name)
  if (!entry) return null
  return { tier: entry.tier as Tier, tags: entry.tags, note: entry.note }
}

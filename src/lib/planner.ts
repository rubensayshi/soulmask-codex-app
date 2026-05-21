import type { Tribesman, TraitMatch, SlotState } from './types'

export type PlannerMode = 'trainee-first' | 'traits-first'

const MAX_SLOTS = 6

export function buildSlots(trainee: Tribesman): SlotState[] {
  const hexTraits = trainee.traits.filter(t => t.shape === 'hexagon')
  const slots: SlotState[] = hexTraits.slice(0, MAX_SLOTS).map(t => ({
    type: 'keep' as const,
    originalTrait: t,
  }))
  while (slots.length < MAX_SLOTS) {
    slots.push({ type: 'empty' as const })
  }
  return slots
}

export interface PoolTrait {
  id: string
  name: string
  icon_name: string
  eff: string
  star: number
  mentorCount: number
}

export function buildTraitPool(
  roster: Tribesman[],
  traineeClan: string,
  keptTraitIds: Set<string>,
  clanExclusiveIds?: Map<string, string>,
  minMentorLevel = 50,
): PoolTrait[] {
  const mentors = roster.filter(tm => tm.level >= minMentorLevel)
  const pool = new Map<string, PoolTrait>()

  for (const mentor of mentors) {
    for (const t of mentor.traits) {
      if (t.shape !== 'hexagon') continue
      if (keptTraitIds.has(t.id)) continue
      if (clanExclusiveIds) {
        const requiredClan = clanExclusiveIds.get(t.id)
        if (requiredClan && requiredClan !== traineeClan.toLowerCase()) continue
      }
      const existing = pool.get(t.id)
      if (existing) {
        existing.mentorCount++
        if (t.star > existing.star) {
          existing.star = t.star
          existing.name = t.name
          existing.eff = t.eff
          existing.icon_name = t.icon_name
        }
      } else {
        pool.set(t.id, {
          id: t.id,
          name: t.name,
          icon_name: t.icon_name,
          eff: t.eff,
          star: t.star,
          mentorCount: 1,
        })
      }
    }
  }

  return Array.from(pool.values()).sort((a, b) => a.name.localeCompare(b.name))
}

export interface RankedMentor {
  tribesman: Tribesman
  desiredTraits: TraitMatch[]
  totalNormal: number
  score: number
}

export function rankMentors(
  roster: Tribesman[],
  desiredTraitIds: Set<string>,
  minMentorLevel = 50,
): RankedMentor[] {
  const results: RankedMentor[] = []

  for (const tm of roster) {
    if (tm.level < minMentorLevel) continue
    const normalTraits = tm.traits.filter(t => t.shape === 'hexagon')
    if (normalTraits.length === 0) continue
    const desired = normalTraits.filter(t => desiredTraitIds.has(t.id))
    if (desired.length === 0) continue
    results.push({
      tribesman: tm,
      desiredTraits: desired,
      totalNormal: normalTraits.length,
      score: desired.length / normalTraits.length,
    })
  }

  return results.sort((a, b) => b.score - a.score || b.desiredTraits.length - a.desiredTraits.length)
}

export interface RankedTrainee {
  tribesman: Tribesman
  alreadyHas: TraitMatch[]
  emptySlots: number
  needsReplacement: number
  score: number
}

export function rankTrainees(
  roster: Tribesman[],
  desiredTraitIds: Set<string>,
): RankedTrainee[] {
  if (desiredTraitIds.size === 0) return []
  const results: RankedTrainee[] = []

  for (const tm of roster) {
    const hexTraits = tm.traits.filter(t => t.shape === 'hexagon')
    const alreadyHas = hexTraits.filter(t => desiredTraitIds.has(t.id))
    const emptySlots = Math.max(0, MAX_SLOTS - hexTraits.length)
    const slotsNeeded = desiredTraitIds.size - alreadyHas.length
    const needsReplacement = Math.max(0, slotsNeeded - emptySlots)
    results.push({
      tribesman: tm,
      alreadyHas,
      emptySlots,
      needsReplacement,
      score: alreadyHas.length / desiredTraitIds.size,
    })
  }

  return results.sort((a, b) =>
    b.score - a.score
    || a.needsReplacement - b.needsReplacement
    || b.emptySlots - a.emptySlots,
  )
}

export function buildSlotsFromDesired(
  trainee: Tribesman,
  desiredTraitIds: Set<string>,
): SlotState[] {
  const hexTraits = trainee.traits.filter(t => t.shape === 'hexagon')
  const slots: SlotState[] = hexTraits.slice(0, MAX_SLOTS).map(t => {
    if (desiredTraitIds.has(t.id)) {
      return { type: 'keep' as const, originalTrait: t }
    }
    return { type: 'replace' as const, originalTrait: t }
  })
  const alreadyPlanned = new Set(hexTraits.filter(t => desiredTraitIds.has(t.id)).map(t => t.id))
  for (const id of desiredTraitIds) {
    if (slots.length >= MAX_SLOTS) break
    if (alreadyPlanned.has(id)) continue
    slots.push({ type: 'planned' as const, desiredTraitId: id })
  }
  while (slots.length < MAX_SLOTS) {
    slots.push({ type: 'empty' as const })
  }
  return slots
}

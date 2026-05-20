import { useState, useMemo, useCallback } from 'react'
import type { SlotState, TraitMatch, Tribesman } from '../lib/types'
import { buildSlots, buildSlotsFromDesired, buildTraitPool, type PlannerMode } from '../lib/planner'
import { clanExclusiveIds } from '../lib/traits'
import { TraineePanel } from '../components/TraineePanel'
import { TraitPicker } from '../components/TraitPicker'
import { MentorPanel } from '../components/MentorPanel'
import { TraineeRankPanel } from '../components/TraineeRankPanel'

export function TrainingPlanner({ roster }: { roster: Tribesman[] }) {

  const [mode, setMode] = useState<PlannerMode>('trainee-first')
  const [traineeId, setTraineeId] = useState<string | null>(null)
  const [slots, setSlots] = useState<SlotState[]>(Array.from({ length: 6 }, () => ({ type: 'empty' as const })))
  const [useForgetfulness, setUseForgetfulness] = useState(false)
  const [activeSlotIdx, setActiveSlotIdx] = useState<number | null>(0)
  const [traitSearch, setTraitSearch] = useState('')

  const trainee = roster.find(tm => tm.id === traineeId) ?? null

  const firstFillable = (sl: SlotState[]) =>
    sl.findIndex(s => s.type === 'empty' || s.type === 'replace')

  const handleSwitchMode = useCallback((next: PlannerMode) => {
    setMode(next)
    setTraineeId(null)
    setSlots(Array.from({ length: 6 }, () => ({ type: 'empty' as const })))
    setActiveSlotIdx(0)
    setUseForgetfulness(false)
    setTraitSearch('')
  }, [])

  const handleSelectTrainee = useCallback((id: string) => {
    setTraineeId(id)
    const tm = roster.find(t => t.id === id)
    if (tm) {
      const next = buildSlots(tm)
      setSlots(next)
      setActiveSlotIdx(firstFillable(next) === -1 ? null : firstFillable(next))
      setTraitSearch('')
    }
  }, [roster])

  const handleSelectTraineeFromRank = useCallback((id: string) => {
    const tm = roster.find(t => t.id === id)
    if (!tm) return
    const currentDesired = new Set(
      slots.filter(s => s.type === 'planned' && s.desiredTraitId).map(s => s.desiredTraitId!),
    )
    const next = buildSlotsFromDesired(tm, currentDesired)
    setTraineeId(id)
    setSlots(next)
    setUseForgetfulness(true)
    setActiveSlotIdx(firstFillable(next) === -1 ? null : firstFillable(next))
    setMode('trainee-first')
  }, [roster, slots])

  const handleToggleKeep = useCallback((idx: number) => {
    setSlots(prev => prev.map((s, i) => {
      if (i !== idx) return s
      if (s.type === 'keep') return { ...s, type: 'replace' as const }
      if (s.type === 'replace') return { ...s, type: 'keep' as const }
      return s
    }))
  }, [])

  const handleSlotClick = useCallback((idx: number) => {
    const slot = slots[idx]
    if (slot.type === 'empty' || slot.type === 'planned' || slot.type === 'replace') {
      setActiveSlotIdx(idx)
    }
  }, [slots])

  const handleClearSlot = useCallback((idx: number) => {
    setSlots(prev => prev.map((s, i) => {
      if (i !== idx) return s
      if (s.originalTrait) return { type: 'replace' as const, originalTrait: s.originalTrait }
      return { type: 'empty' as const }
    }))
    setActiveSlotIdx(idx)
  }, [])

  const handleToggleForgetfulness = useCallback(() => {
    setUseForgetfulness(prev => {
      if (prev) {
        setSlots(s => s.map(slot =>
          slot.type === 'replace' ? { ...slot, type: 'keep' as const } : slot
        ))
      }
      return !prev
    })
  }, [])

  const keptTraitIds = useMemo(
    () => new Set(slots.filter(s => s.type === 'keep' && s.originalTrait).map(s => s.originalTrait!.id)),
    [slots],
  )

  const desiredTraitIds = useMemo(
    () => new Set(slots.filter(s => s.type === 'planned' && s.desiredTraitId).map(s => s.desiredTraitId!)),
    [slots],
  )

  const pool = useMemo(
    () => buildTraitPool(roster, trainee?.clan ?? '', keptTraitIds, clanExclusiveIds),
    [roster, trainee?.clan, keptTraitIds],
  )

  const traitLookup = useMemo(() => {
    const map = new Map<string, TraitMatch>()
    for (const tm of roster) {
      for (const t of tm.traits) {
        if (!map.has(t.id) || t.star > map.get(t.id)!.star) map.set(t.id, t)
      }
    }
    return map
  }, [roster])

  const handleSelectTrait = useCallback((traitId: string) => {
    if (activeSlotIdx === null) return
    if (desiredTraitIds.has(traitId) || keptTraitIds.has(traitId)) return
    setSlots(prev => {
      const next = prev.map((s, i) => {
        if (i !== activeSlotIdx) return s
        return { ...s, type: 'planned' as const, desiredTraitId: traitId }
      })
      const nextIdx = firstFillable(next)
      setActiveSlotIdx(nextIdx === -1 ? null : nextIdx)
      return next
    })
    setTraitSearch('')
  }, [activeSlotIdx, desiredTraitIds, keptTraitIds])

  const focusTraitId = activeSlotIdx !== null && slots[activeSlotIdx]?.type === 'planned'
    ? slots[activeSlotIdx].desiredTraitId ?? null
    : null

  return (
    <div className="grid h-full min-h-0" style={{ gridTemplateColumns: '240px 1fr 280px' }}>
      <div className="border-r border-border-soft overflow-hidden" style={{ background: 'oklch(0.155 0.006 130)' }}>
        <TraineePanel
          roster={roster}
          traineeId={traineeId}
          onSelectTrainee={handleSelectTrainee}
          slots={slots}
          activeSlotIdx={activeSlotIdx}
          onSlotClick={handleSlotClick}
          onToggleKeep={handleToggleKeep}
          onClearSlot={handleClearSlot}
          useForgetfulness={useForgetfulness}
          onToggleForgetfulness={handleToggleForgetfulness}
          traitLookup={traitLookup}
          mode={mode}
          onSwitchMode={handleSwitchMode}
        />
      </div>
      <div className="border-r border-border-soft overflow-hidden">
        <TraitPicker
          pool={pool}
          search={traitSearch}
          onSearchChange={setTraitSearch}
          selectedIds={desiredTraitIds}
          onSelect={handleSelectTrait}
          activeSlotIdx={activeSlotIdx}
        />
      </div>
      <div className="overflow-hidden">
        {mode === 'traits-first' && !traineeId ? (
          <TraineeRankPanel
            roster={roster}
            desiredTraitIds={desiredTraitIds}
            onSelectTrainee={handleSelectTraineeFromRank}
          />
        ) : (
          <MentorPanel
            roster={roster}
            desiredTraitIds={desiredTraitIds}
            focusTraitId={focusTraitId}
            traineeId={traineeId}
          />
        )}
      </div>
    </div>
  )
}

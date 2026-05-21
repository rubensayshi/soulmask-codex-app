import { create } from 'zustand'
import type { Tribesman, ProcessResult, TraitMatch, ClanName, StatusType, Alternative } from './types'
import { getBestTrait, getTierForIcon, getTierForName } from './traits'
import { normalizeTitle, normalizeClass, normalizeGroup, deduplicateGroups } from './fuzzy'

// ── Sidecar output shape (class instead of klass, group/status as strings, no id/prof) ──
interface RawTribesman {
  name?: string
  level?: number | null
  class?: string | null
  klass?: string | null
  clan?: string | null
  title?: string | null
  status?: string | null
  group?: string | null
  location?: string | null
  traits?: Array<{ icon_name: string; confidence: number; alternatives?: Alternative[] }>
  prof?: number[]
}

function normalizeClan(raw: string | null | undefined): ClanName {
  const known: ClanName[] = ['Claw', 'Flint', 'Fang', 'Wolf', 'Horn', 'Exile', 'DLC']
  if (!raw) return 'Exile'
  const match = known.find(c => c.toLowerCase() === raw.toLowerCase())
  if (match) return match
  const remaps: Record<string, ClanName> = { outcast: 'Exile', long: 'Horn' }
  return remaps[raw.toLowerCase()] ?? 'Exile'
}

function normalizeStatus(raw: string | null | undefined): StatusType {
  if (!raw) return 'idle'
  const map: Record<string, StatusType> = {
    'idle': 'idle', 'hosting': 'hosting', 'mining': 'mining',
    'resting': 'resting', 'work break': 'work-break',
  }
  return map[raw.toLowerCase()] ?? 'idle'
}

function normalizeTribesman(raw: RawTribesman, capturedAt: string): Tribesman {
  const rawTraits = raw.traits ?? []
  const seen = new Set<string>()
  const allTraits: TraitMatch[] = []
  for (const t of rawTraits) {
    if (seen.has(t.icon_name)) continue
    seen.add(t.icon_name)
    const info = getBestTrait(t.icon_name)
    const tierInfo = getTierForIcon(t.icon_name) ?? (info?.name ? getTierForName(info.name) : null)
    allTraits.push({
      icon_name: t.icon_name,
      confidence: t.confidence,
      alternatives: t.alternatives,
      id: info?.id ?? t.icon_name,
      name: info?.name ?? info?.name_zh ?? t.icon_name,
      shape: info?.shape ?? 'hexagon',
      eff: info?.description ?? '',
      star: info?.star ?? 1,
      tier: tierInfo?.tier ?? null,
      tier_tags: tierInfo?.tags,
      tier_note: tierInfo?.note,
    })
  }
  const MAX_HEXAGON = 6
  const hexTraits = allTraits.filter(t => t.shape === 'hexagon')
  const otherTraits = allTraits.filter(t => t.shape !== 'hexagon')
  const cappedHex = hexTraits.length > MAX_HEXAGON
    ? hexTraits.sort((a, b) => b.confidence - a.confidence).slice(0, MAX_HEXAGON)
    : hexTraits
  const traits = [...cappedHex, ...otherTraits]
  const name = String(raw.name ?? '')
  return {
    id: name ? name.toLowerCase().replace(/[^a-z0-9]+/g, '_') : `tm_${Date.now()}`,
    name,
    level: raw.level ?? 0,
    klass: normalizeClass(raw.class ?? raw.klass),
    clan: normalizeClan(raw.clan),
    group: normalizeGroup(raw.group),
    title: normalizeTitle(raw.title),
    location: raw.location ?? '',
    status: normalizeStatus(raw.status),
    traits,
    prof: raw.prof ?? Array(8).fill(0),
    captured_at: capturedAt,
  }
}

const REVIEW_THRESHOLD = 0.80

export interface ReviewItem {
  id: string
  tribesmanId: string
  tribesmanName: string
  traitIndex: number
  cropLabel: string
  field: 'trait'
  options: Array<{ id: string; name: string; pct: number }>
}

export type CaptureStatus = 'idle' | 'capturing' | 'processing' | 'done' | 'error'

export type LogLevel = 'info' | 'success' | 'error'

export interface LogEntry {
  id: number
  time: string
  level: LogLevel
  message: string
}

let logSeq = 0

interface RosterState {
  tribesmen: Tribesman[]
  initialized: boolean
  lastUpdated: string | null
  captureStatus: CaptureStatus
  captureError: string | null
  lastCaptureCount: number | null
  queueCount: number
  processProgress: string | null
  captureLog: LogEntry[]
  reviewQueue: ReviewItem[]

  loadRoster: (roster: { last_updated: string; tribesmen: unknown[] }) => void
  markInitialized: () => void
  clearRoster: () => void
  setCaptureStatus: (s: CaptureStatus) => void
  setCaptureError: (e: string) => void
  setQueueCount: (n: number) => void
  setProgress: (p: string | null) => void
  logQueuedPath: (path: string) => void
  addCaptureResult: (result: ProcessResult) => void
  clearLog: () => void
  commitReview: (picks: Record<string, string>) => void
  clearReview: () => void
}

function appendLog(state: { captureLog: LogEntry[] }, level: LogLevel, message: string): LogEntry[] {
  const entry: LogEntry = {
    id: ++logSeq,
    time: new Date().toLocaleTimeString('en-GB', { hour12: false }),
    level,
    message,
  }
  return [...state.captureLog, entry]
}

function loadSessionState(): Partial<RosterState> | undefined {
  if (!import.meta.env.DEV || '__TAURI_INTERNALS__' in window) return undefined
  try {
    const raw = sessionStorage.getItem('roster_dev')
    return raw ? JSON.parse(raw) : undefined
  } catch { return undefined }
}

const _devState = loadSessionState()

export const useRosterStore = create<RosterState>((set) => ({
  tribesmen: _devState?.tribesmen ?? [],
  initialized: _devState?.initialized ?? false,
  lastUpdated: _devState?.lastUpdated ?? null,
  captureStatus: 'idle',
  captureError: null,
  lastCaptureCount: null,
  queueCount: 0,
  processProgress: null,
  captureLog: [],
  reviewQueue: [],

  loadRoster: (roster) => {
    const now = new Date().toISOString()
    const tribesmen = (roster.tribesmen as unknown[]).map(t => {
      const raw = t as RawTribesman & { id?: string; star?: number }
      return normalizeTribesman(raw, (raw as { captured_at?: string }).captured_at ?? now)
    })
    const groupRemap = deduplicateGroups(tribesmen)
    if (groupRemap.size > 0) {
      for (const t of tribesmen) {
        const mapped = groupRemap.get(t.group)
        if (mapped) t.group = mapped
      }
    }
    return set({ tribesmen, lastUpdated: roster.last_updated, initialized: true })
  },

  markInitialized: () => set({ initialized: true }),

  clearRoster: () => set({ tribesmen: [], lastUpdated: null, initialized: true }),

  setCaptureStatus: (s) => set((state) => ({
    captureStatus: s,
    captureError: null,
    captureLog: appendLog(state, 'info',
      s === 'capturing' ? 'Hotkey triggered — capturing screen…'
      : s === 'processing' ? 'Screenshot saved — running OCR…'
      : `Status: ${s}`
    ),
  })),

  setCaptureError: (e) => set((state) => ({
    captureStatus: 'error',
    captureError: e,
    captureLog: appendLog(state, 'error', e),
  })),

  setQueueCount: (n) => set((state) => {
    if (n === state.queueCount) return {}
    const msg = n === 0
      ? 'Queue cleared'
      : `Screenshot ${n} queued — Alt+Shift+P to process`
    return {
      queueCount: n,
      captureLog: appendLog(state, 'info', msg),
    }
  }),

  setProgress: (p) => set({ processProgress: p }),

  logQueuedPath: (path) => set((state) => ({
    captureLog: appendLog(state, 'info', `Saved: ${path}`),
  })),

  addCaptureResult: (result) => set((state) => {
    try {
      const now = new Date().toISOString()
      const incoming = result.tribesmen.map(t => normalizeTribesman(t as unknown as RawTribesman, now))
      const merged = [...state.tribesmen]
      for (const t of incoming) {
        const idx = merged.findIndex(m => m.name === t.name)
        if (idx >= 0) merged[idx] = t
        else merged.push(t)
      }
      const groupRemap = deduplicateGroups(merged)
      if (groupRemap.size > 0) {
        for (const t of merged) {
          const mapped = groupRemap.get(t.group)
          if (mapped) t.group = mapped
        }
      }

      const incomingIds = new Set(incoming.map(t => t.id))
      const keptReviews = state.reviewQueue.filter(r => !incomingIds.has(r.tribesmanId))
      const newReviews: ReviewItem[] = []
      for (const t of incoming) {
        t.traits.forEach((trait, idx) => {
          if (trait.confidence < REVIEW_THRESHOLD && trait.alternatives?.length) {
            const options = [
              { id: trait.icon_name, name: trait.name, pct: Math.round(trait.confidence * 100) },
              ...trait.alternatives.map(alt => {
                const info = getBestTrait(alt.icon_name)
                return {
                  id: alt.icon_name,
                  name: info?.name ?? info?.name_zh ?? alt.icon_name,
                  pct: Math.round(alt.confidence * 100),
                }
              }),
            ]
            newReviews.push({
              id: `${t.id}__trait__${idx}`,
              tribesmanId: t.id,
              tribesmanName: t.name,
              traitIndex: idx,
              cropLabel: `TRAIT ICON · ${idx + 1}`,
              field: 'trait',
              options,
            })
          }
        })
      }

      const names = incoming.map(t => t.name).join(', ')
      return {
        tribesmen: merged,
        lastUpdated: now,
        captureStatus: 'done',
        processProgress: null,
        lastCaptureCount: result.cards_found,
        reviewQueue: [...keptReviews, ...newReviews],
        captureLog: appendLog(state, 'success',
          `Found ${result.cards_found} card${result.cards_found !== 1 ? 's' : ''}, ${incoming.length} tribesman${incoming.length !== 1 ? 'en' : ''}${names ? ': ' + names : ''}`
        ),
      }
    } catch (err) {
      const msg = err instanceof Error ? `${err.message}\n${err.stack}` : String(err)
      return {
        captureStatus: 'error' as CaptureStatus,
        captureError: String(err),
        captureLog: appendLog(state, 'error', `Normalization failed: ${msg}`),
      }
    }
  }),

  commitReview: (picks) => set((state) => {
    const tribesmen = [...state.tribesmen]
    const committed = new Set<string>()
    for (const [reviewId, chosenIconName] of Object.entries(picks)) {
      const item = state.reviewQueue.find(r => r.id === reviewId)
      if (!item) continue
      const tIdx = tribesmen.findIndex(t => t.id === item.tribesmanId)
      if (tIdx < 0) continue
      const t = { ...tribesmen[tIdx], traits: [...tribesmen[tIdx].traits] }
      const trait = t.traits[item.traitIndex]
      if (!trait || trait.icon_name === chosenIconName) {
        committed.add(reviewId)
        continue
      }
      const info = getBestTrait(chosenIconName)
      const tierInfo = getTierForIcon(chosenIconName) ?? (info?.name ? getTierForName(info.name) : null)
      t.traits[item.traitIndex] = {
        ...trait,
        icon_name: chosenIconName,
        id: info?.id ?? chosenIconName,
        name: info?.name ?? info?.name_zh ?? chosenIconName,
        shape: info?.shape ?? trait.shape,
        eff: info?.description ?? '',
        star: info?.star ?? 1,
        tier: tierInfo?.tier ?? null,
        tier_tags: tierInfo?.tags,
        tier_note: tierInfo?.note,
      }
      tribesmen[tIdx] = t
      committed.add(reviewId)
    }
    return {
      tribesmen,
      reviewQueue: state.reviewQueue.filter(r => !committed.has(r.id)),
    }
  }),

  clearReview: () => set({ reviewQueue: [] }),

  clearLog: () => set({ captureLog: [] }),
}))

if (import.meta.env.DEV && !('__TAURI_INTERNALS__' in window)) {
  useRosterStore.subscribe((s) => {
    try {
      sessionStorage.setItem('roster_dev', JSON.stringify({
        tribesmen: s.tribesmen,
        initialized: s.initialized,
        lastUpdated: s.lastUpdated,
      }))
    } catch { /* quota exceeded — ignore */ }
  })
}

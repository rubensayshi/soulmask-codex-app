import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Tier } from './types'
import { getTierForIcon as getDefaultTier } from './traits'

interface TierOverride {
  tier: Tier
}

interface TierState {
  overrides: Record<string, TierOverride>
  setTier: (iconName: string, tier: Tier) => void
  removeTier: (iconName: string) => void
  importOverrides: (data: Record<string, TierOverride>) => void
  resetAll: () => void
}

export const useTierStore = create<TierState>()(
  persist(
    (set) => ({
      overrides: {},
      setTier: (iconName, tier) =>
        set(s => ({ overrides: { ...s.overrides, [iconName]: { tier } } })),
      removeTier: (iconName) =>
        set(s => {
          const { [iconName]: _, ...rest } = s.overrides
          return { overrides: rest }
        }),
      importOverrides: (data) => set({ overrides: data }),
      resetAll: () => set({ overrides: {} }),
    }),
    { name: 'soulmask-tier-overrides' },
  ),
)

export function useEffectiveTier(iconName: string, defaultTier?: Tier | null): Tier | null {
  const override = useTierStore(s => s.overrides[iconName])
  if (override) return override.tier
  return defaultTier ?? getDefaultTier(iconName)?.tier ?? null
}

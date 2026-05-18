import { useMemo } from 'react'
import type { Tribesman } from '../lib/types'
import { rankTrainees, type RankedTrainee } from '../lib/planner'
import { CLANS } from '../lib/data'

interface Props {
  roster: Tribesman[]
  desiredTraitIds: Set<string>
  onSelectTrainee: (id: string) => void
}

export function TraineeRankPanel({ roster, desiredTraitIds, onSelectTrainee }: Props) {
  const ranked = useMemo(
    () => rankTrainees(roster, desiredTraitIds),
    [roster, desiredTraitIds],
  )

  return (
    <div className="flex flex-col gap-3 h-full overflow-y-auto content-scroll" style={{ padding: 16 }}>
      <span
        className="uppercase"
        style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', letterSpacing: '0.1em' }}
      >
        Best trainee candidates
      </span>

      {desiredTraitIds.size === 0 && (
        <div style={{ fontSize: 12, color: 'var(--color-faint)', fontStyle: 'italic', padding: '20px 0', textAlign: 'center' }}>
          Pick desired traits to see which tribesmen are the best base.
        </div>
      )}

      {desiredTraitIds.size > 0 && ranked.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--color-faint)', fontStyle: 'italic', padding: '20px 0', textAlign: 'center' }}>
          No roster members found.
        </div>
      )}

      <div className="flex flex-col gap-2">
        {ranked.map(m => (
          <TraineeCard key={m.tribesman.id} ranked={m} onSelect={() => onSelectTrainee(m.tribesman.id)} />
        ))}
      </div>
    </div>
  )
}

function TraineeCard({ ranked, onSelect }: { ranked: RankedTrainee; onSelect: () => void }) {
  const { tribesman: tm, alreadyHas, emptySlots, needsReplacement, score } = ranked
  const pct = Math.round(score * 100)
  const isGood = pct >= 50

  return (
    <button
      className="rounded-[var(--radius)] text-left w-full transition-colors hover:brightness-110"
      style={{
        padding: '10px 12px',
        background: isGood ? 'oklch(0.80 0.06 140 / 0.04)' : 'oklch(0.19 0.008 130 / 0.4)',
        border: `1px solid ${isGood ? 'oklch(0.80 0.06 140 / 0.12)' : 'var(--color-border-soft)'}`,
      }}
      onClick={onSelect}
    >
      <div className="flex justify-between items-center" style={{ marginBottom: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-serif)' }}>
          {tm.name}
        </span>
        <span style={{ fontSize: 20, fontWeight: 700, color: isGood ? 'var(--color-accent)' : 'var(--color-text-dim)' }}>
          {pct}%
        </span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', marginBottom: 8 }}>
        Lv.{tm.level} · {tm.clan}
        <span className="inline-block w-1.5 h-1.5 rounded-full ml-1.5" style={{ background: CLANS[tm.clan]?.hue, verticalAlign: 'middle' }} />
      </div>

      {alreadyHas.length > 0 && (
        <div className="flex flex-wrap gap-1" style={{ marginBottom: 4 }}>
          {alreadyHas.map(t => (
            <span
              key={t.id}
              className="inline-flex items-center rounded-full"
              style={{
                padding: '1px 6px',
                fontSize: 11,
                background: 'oklch(0.80 0.06 140 / 0.12)',
                color: 'var(--color-accent)',
              }}
            >
              {t.name}
            </span>
          ))}
        </div>
      )}

      <div style={{ fontSize: 10, color: 'var(--color-faint)', marginTop: 6, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em' }}>
        {alreadyHas.length} already has
        {emptySlots > 0 && <> · {emptySlots} empty slot{emptySlots !== 1 ? 's' : ''}</>}
        {needsReplacement > 0 && <> · {needsReplacement} to replace</>}
      </div>
    </button>
  )
}

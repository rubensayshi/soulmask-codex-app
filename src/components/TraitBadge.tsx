import { useState } from 'react'
import type { BadgeShape, Tier, TraitMatch } from '../lib/types'
import { useEffectiveTier } from '../lib/tierStore'

export const TIER_COLORS: Record<Tier, { bg: string; text: string }> = {
  S: { bg: 'oklch(0.55 0.20 25)',  text: '#fff' },
  A: { bg: 'oklch(0.60 0.16 60)',  text: '#fff' },
  B: { bg: 'oklch(0.52 0.14 300)', text: '#fff' },
  C: { bg: 'oklch(0.45 0.00 0)',   text: '#ccc' },
  D: { bg: 'oklch(0.38 0.03 60)',  text: '#bbb' },
  F: { bg: 'oklch(0.35 0.10 20)',  text: '#daa' },
}

const SHAPE_COLORS: Record<BadgeShape, { stroke: string; fill: string; glyph: string }> = {
  hexagon: { stroke: 'oklch(0.55 0.08 165)', fill: 'oklch(0.20 0.02 165)', glyph: 'oklch(0.70 0.08 165)' },
  shield:  { stroke: 'oklch(0.55 0.08 80)',  fill: 'oklch(0.20 0.02 80)',  glyph: 'oklch(0.70 0.08 80)' },
  diamond: { stroke: 'oklch(0.55 0.06 130)', fill: 'oklch(0.20 0.02 130)', glyph: 'oklch(0.70 0.06 130)' },
}

const SHAPE_PATHS: Record<BadgeShape, string> = {
  hexagon: 'M12,1.5 L22,6.5 L22,17.5 L12,22.5 L2,17.5 L2,6.5 Z',
  diamond: 'M12,1.5 L22.5,12 L12,22.5 L1.5,12 Z',
  shield:  'M12,2 L21,7 L21,14 Q21,20 12,23 Q3,20 3,14 L3,7 Z',
}

const GLYPHS: string[] = [
  'M8 8 L16 16 M16 8 L8 16',
  'M12 6 L12 18 M6 12 L18 12',
  'M12 7 L17 12 L12 17 L7 12 Z',
  'M8 12 Q12 6 16 12 Q12 18 8 12',
  'M7 17 L12 7 L17 17',
  'M12 7 L14 11 L18 12 L14 14 L12 18 L10 14 L6 12 L10 11 Z',
  'M8 8 L16 8 L16 16 L8 16 Z',
  'M9 16 L12 8 L15 16',
  'M7 12 L12 7 L17 12 M7 15 L12 10 L17 15',
  'M12 7 L12 17 M9 10 L15 10 M9 14 L15 14',
]

function hashGlyph(id: string): number {
  let h = 0
  for (let i = 0; i < id.length; i++) h = ((h << 5) - h + id.charCodeAt(i)) | 0
  return Math.abs(h) % GLYPHS.length
}

interface Props {
  trait: TraitMatch
  size?: number
  withPips?: boolean
}

export function TraitBadge({ trait, size = 24, withPips = true }: Props) {
  const [imgErr, setImgErr] = useState(false)
  const c = SHAPE_COLORS[trait.shape]
  const path = SHAPE_PATHS[trait.shape]
  const glyph = GLYPHS[hashGlyph(trait.id)]
  const iconSize = Math.ceil(size * 0.7)

  const tier = useEffectiveTier(trait.icon_name, trait.tier)
  const tc = tier ? TIER_COLORS[tier] : null

  return (
    <span className="inline-flex flex-col items-center" style={{ width: size }}>
      <span className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox="0 0 24 24" className="absolute inset-0">
          <path d={path} fill={c.fill} stroke={c.stroke} strokeWidth="1" />
          {imgErr && (
            <g opacity="0.65">
              <path d={glyph} fill="none" stroke={c.glyph} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            </g>
          )}
        </svg>
        {!imgErr && (
          <img
            src={`/icons/${trait.icon_name}.webp`}
            alt=""
            className="relative object-contain"
            style={{ width: iconSize, height: iconSize }}
            onError={() => setImgErr(true)}
          />
        )}
        {tc && (
          <span
            className="absolute flex items-center justify-center"
            style={{
              top: -3, right: -4,
              width: 11, height: 11,
              borderRadius: '50%',
              background: tc.bg,
              color: tc.text,
              fontSize: 7,
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              lineHeight: 1,
              border: '1px solid oklch(0.16 0.006 130)',
            }}
          >
            {tier}
          </span>
        )}
      </span>
      {withPips && (
        <span className="flex gap-[1.5px]" style={{ marginTop: 1 }}>
          {[1, 2, 3].map(s => (
            <span
              key={s}
              className="rounded-full"
              style={{
                width: 3, height: 3,
                background: s <= trait.star ? 'var(--color-gold)' : 'var(--color-faint)',
              }}
            />
          ))}
        </span>
      )}
    </span>
  )
}

export function TraitBadgeLg({ trait }: { trait: TraitMatch }) {
  const [imgErr, setImgErr] = useState(false)
  const size = 34
  const c = SHAPE_COLORS[trait.shape]
  const path = SHAPE_PATHS[trait.shape]
  const glyph = GLYPHS[hashGlyph(trait.id)]
  const iconSize = Math.ceil(size * 0.7)
  const tier = useEffectiveTier(trait.icon_name, trait.tier)
  const tc = tier ? TIER_COLORS[tier] : null

  return (
    <span className="relative inline-flex items-center justify-center flex-shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox="0 0 24 24" className="absolute inset-0">
        <path d={path} fill={c.fill} stroke={c.stroke} strokeWidth="1" />
        {imgErr && (
          <g opacity="0.65">
            <path d={glyph} fill="none" stroke={c.glyph} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
          </g>
        )}
      </svg>
      {!imgErr && (
        <img
          src={`/icons/${trait.icon_name}.webp`}
          alt=""
          className="relative object-contain"
          style={{ width: iconSize, height: iconSize }}
          onError={() => setImgErr(true)}
        />
      )}
      {tc && (
        <span
          className="absolute flex items-center justify-center"
          style={{
            top: -3, right: -5,
            width: 14, height: 14,
            borderRadius: '50%',
            background: tc.bg,
            color: tc.text,
            fontSize: 8.5,
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            lineHeight: 1,
            border: '1px solid oklch(0.16 0.006 130)',
          }}
        >
          {tier}
        </span>
      )}
    </span>
  )
}

export { SHAPE_COLORS }

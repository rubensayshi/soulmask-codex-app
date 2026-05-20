const KNOWN_TITLES = [
  'Archery Master', 'Axe Killer', 'Blood Drinker', 'Bonebreaker', 'Born Laborer',
  'Born Revolt', 'Butcher In Woods', 'Chest Breaker', 'Death Bringer', 'Expert Craftsman',
  'Expert Slaughter', 'Famous Trash', 'Farming Expert', 'Fate-Choker',
  'Fly Cutter Assassin', 'Hardbone', 'Heartcaptor', 'Lung Piercer', 'Mad Worker',
  'Manual Labor Expert', 'Nightwalker', 'Oppressor', 'Skilled Hand', 'Skilled Work Expert',
  'The Chosen', 'The Dauntless', 'The Flammable', 'The Unburned', 'Unlucky One',
  'Weapon Master',
]

const CLASS_RANKS = ['Novice', 'Skilled', 'Master']
const CLASS_ROLES = ['Guard', 'Craftsman', 'Hunter', 'Warrior', 'Laborer']

const KNOWN_CLASSES: string[] = []
for (const rank of CLASS_RANKS) {
  for (const role of CLASS_ROLES) {
    KNOWN_CLASSES.push(`${rank} ${role}`)
  }
}

const CLASS_SET = new Set(KNOWN_CLASSES.map(c => c.toLowerCase()))

function editDistance(a: string, b: string): number {
  const la = a.length
  const lb = b.length
  const dp: number[][] = Array.from({ length: la + 1 }, () => Array(lb + 1).fill(0))
  for (let i = 0; i <= la; i++) dp[i][0] = i
  for (let j = 0; j <= lb; j++) dp[0][j] = j
  for (let i = 1; i <= la; i++) {
    for (let j = 1; j <= lb; j++) {
      dp[i][j] = a[i - 1] === b[j - 1]
        ? dp[i - 1][j - 1]
        : 1 + Math.min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])
    }
  }
  return dp[la][lb]
}

function bestMatch(raw: string, candidates: string[], threshold: number): string | null {
  const cleaned = raw.replace(/[^a-zA-Z\s-]/g, '').replace(/\s+/g, ' ').trim()
  if (!cleaned) return null

  const lc = cleaned.toLowerCase()
  for (const c of candidates) {
    if (c.toLowerCase() === lc) return c
  }

  let best: string | null = null
  let bestDist = Infinity
  for (const c of candidates) {
    const dist = editDistance(lc, c.toLowerCase())
    if (dist < bestDist) {
      bestDist = dist
      best = c
    }
  }

  const maxLen = Math.max(cleaned.length, best?.length ?? 0)
  if (best && maxLen > 0 && bestDist / maxLen <= threshold) return best
  return null
}

export function normalizeTitle(raw: string | null | undefined): string {
  if (!raw || raw === '—' || raw === '-') return '—'
  if (CLASS_SET.has(raw.toLowerCase())) return '—'
  const cleaned = raw.replace(/[^a-zA-Z\s-]/g, '').replace(/\s+/g, ' ').trim()
  if (CLASS_SET.has(cleaned.toLowerCase())) return '—'
  const match = bestMatch(raw, KNOWN_TITLES, 0.35)
  return match ?? '—'
}

export function normalizeClass(raw: string | null | undefined): string {
  if (!raw) return ''
  const match = bestMatch(raw, KNOWN_CLASSES, 0.4)
  return match ?? raw
}

export function normalizeGroup(raw: string | null | undefined): string {
  if (!raw || raw === 'unassigned') return 'Ungrouped'

  const cleaned = raw.replace(/[^a-zA-Z\s]/g, '').replace(/\s+/g, ' ').trim()
  if (!cleaned) return 'Ungrouped'

  const lc = cleaned.toLowerCase()
  if (lc === 'ungrouped' || editDistance(lc, 'ungrouped') <= 2) return 'Ungrouped'

  const words = cleaned.split(' ')
  const meaningful = words.filter(w => w.length >= 3)
  return meaningful.length > 0 ? meaningful.join(' ') : cleaned
}

export function deduplicateGroups(tribesmen: Array<{ group: string }>): Map<string, string> {
  const counts = new Map<string, number>()
  for (const t of tribesmen) {
    counts.set(t.group, (counts.get(t.group) ?? 0) + 1)
  }

  const canonical = Array.from(counts.entries())
    .filter(([, n]) => n >= 2)
    .map(([g]) => g)
    .sort((a, b) => (counts.get(b) ?? 0) - (counts.get(a) ?? 0))

  const remap = new Map<string, string>()
  for (const [group] of counts) {
    if (group === 'Ungrouped') continue
    if (canonical.includes(group)) continue

    let match = bestMatch(group, canonical, 0.4)
    if (!match) {
      const lc = group.toLowerCase()
      for (const c of canonical) {
        if (lc.endsWith(c.toLowerCase()) || lc.startsWith(c.toLowerCase())) {
          match = c
          break
        }
      }
    }
    if (match) remap.set(group, match)
  }
  return remap
}

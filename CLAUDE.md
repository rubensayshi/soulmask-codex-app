# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Soulmask Codex App — a Tauri 2 desktop application for managing Soulmask tribesman rosters via screen capture and OCR. Three layers:

1. **Frontend** (React 18 + Vite 6 + TypeScript + Tailwind v4) — SPA with roster table, training planner, capture UI
2. **Rust backend** (Tauri 2, crate name `screenread`) — screen capture via `xcap`, global hotkey, sidecar management
3. **Python sidecar** — OpenCV + Tesseract pipeline for card detection, OCR, and trait icon matching

## Commands

```bash
pnpm dev                # Vite dev server on :1420 (browser-only, no Tauri)
pnpm tauri dev          # Full Tauri app with hot reload (main repo only)
pnpm tauri:dev          # Full Tauri app with hot reload (worktree-safe, dynamic port)
pnpm build              # tsc + vite build (frontend production bundle)
pnpm typecheck          # tsc --noEmit

# Python sidecar
cd sidecar && source .venv/bin/activate
python process.py <screenshot.png> --atlas ../assets/atlas   # standalone test
pytest test_detect_cards.py -v                                # single test file
pytest                                                        # all sidecar tests

# Rust
cd src-tauri && cargo check
cd src-tauri && cargo build
```

## Key paths

| What            | Path                 | Notes                                    |
| --------------- | -------------------- | ---------------------------------------- |
| Frontend source | `src/`               | React + Vite                             |
| Tauri backend   | `src-tauri/`         | Rust, crate `screenread`                 |
| Python sidecar  | `sidecar/`           | OCR pipeline, `requirements.txt`         |
| Trait data       | `assets/traits.json` | Trait definitions keyed by `icon_name`   |
| Trait atlas      | `assets/atlas/`      | Reference PNGs for template matching     |
| Test fixtures   | `fixtures/`          | Screenshot samples for OCR tuning        |
| Design docs     | `docs/`              | UI spec, design docs, plans              |
| Dev scripts     | `scripts/`           | Worktree port helpers (`dev-port.cjs`)   |

## Architecture

### Data flow: capture -> roster

1. **Global hotkey** (Alt+Shift+S) registered in `src-tauri/src/lib.rs` triggers `capture_and_process()` in `commands.rs`
2. Rust captures primary monitor via `xcap`, saves temp PNG, spawns `python3 sidecar/process.py <path> --atlas <atlas_dir>`
3. Sidecar pipeline (4 stages):
   - `detect_cards.py` — morphological line detection finds 2-column card grid, returns `Card` bounding boxes
   - `ocr_text.py` — Tesseract OCR on cropped card regions (name, level/class/clan, status, group). Dual-channel OCR (grayscale + red channel) for purple game text
   - `match_traits.py` — segments hexagonal icons from trait row, template-matches against atlas PNGs (`cv2.matchTemplate`)
   - `merge.py` — deduplicates tribesmen across multi-screenshot captures via fuzzy name matching (edit distance < 0.35), picks best OCR result per field
4. JSON result returned via stdout, Rust deserializes and emits Tauri events (`capture:status`, `capture:result`, `capture:error`)
5. Frontend listens via `@tauri-apps/api/event`, Zustand store (`src/lib/store.ts`) merges incoming tribesmen by name

### Frontend state

- **Zustand store** (`src/lib/store.ts`) — single store for roster data + capture status/log. Tribesmen merged by name on each capture
- **Trait resolution** (`src/lib/traits.ts`) — maps `icon_name` from OCR to `TraitInfo` from `assets/traits.json`. Indexed by `icon_name`, uses highest-star variant
- **Training planner** (`src/lib/planner.ts`) — mentors must be Lv.50+. Ranks mentors by `desired_traits / total_hexagon_traits`. Ranks trainees by how many desired traits they already have + empty slot count

### Card layout constants

`detect_cards.py:LAYOUT` defines fractional regions within each card crop. These are tuned against specific fixture resolutions — change them carefully and re-test against `fixtures/debug-*.png`.

## Conventions

- **Trait shapes**: hexagon = learned (trainable), diamond = preference, shield = innate. Only hexagons appear in planner
- **Mentors**: must be Lv.50+ to appear in training planner pool
- **Mock data**: `src/lib/data.ts` has generated mock roster data. Not loaded automatically — use Settings > Developer > "Load mock data" button in the UI (DEV mode only) when you need test data
- **Screen capture hotkey**: Alt+Shift+S, registered via `tauri-plugin-global-shortcut`
- **OCR thresholds**: game text is light-on-dark with semi-transparent backgrounds. OCR uses multiple threshold/channel combinations and merges results. Tuning values are in `ocr_text.py`
- **Clan name mapping**: OCR frequently mangles clan names; `ocr_text.py` has a hardcoded `CLAN_MAP` fuzzy lookup table
- **Feature flags**: `ENABLE_PROFICIENCIES` in `data.ts` gates the proficiency columns (currently `false`)
- **Worktree dev ports**: `scripts/dev-port.cjs` hashes the repo path to derive a unique Vite port per worktree (main repo = 1420, worktrees = 1100-1999). `pnpm dev` picks this up automatically; for Tauri use `pnpm tauri:dev` which passes the matching `devUrl` override

## Related projects

- **souldb** (`/Users/ruben/work/private/souldb`) — Soulmask webapp with comprehensive game data: traits (1,300+ with English translations, star levels, effects, community tier rankings), items, recipes, tech tree, creature spawns. SQLite database at `data/app.db`, translations at `data/translations/`. This repo's `assets/traits.json` was enriched from souldb's trait data. Useful for looking up game mechanics, adding new data fields, or cross-referencing OCR output.

## Styling

Dark fantasy/cartography theme using oklch color space. Design tokens in `src/styles.css` under `@theme`. Fonts: Cormorant Garamond (headings), Manrope (body), IBM Plex Mono (code/data). Per-clan accent colors via `--color-hue-{clan}` CSS vars.

# CLAUDE.md

## What this is

Soulmask Codex App — a Tauri 2 desktop application for managing Soulmask tribesman rosters via screen capture and OCR.

Three layers:

1. **Frontend** (React + Vite + TypeScript + Tailwind) — SPA with roster table, training planner, capture UI
2. **Rust backend** (Tauri 2) — screen capture via `xcap`, global shortcuts, sidecar management
3. **Python sidecar** — OpenCV + Tesseract pipeline for card detection, OCR, and trait icon matching

## Key paths

| What             | Path                    | Notes                              |
| ---------------- | ----------------------- | ---------------------------------- |
| Frontend source  | `src/`                  | React + Vite                       |
| Tauri backend    | `src-tauri/`            | Rust, Cargo workspace              |
| Python sidecar   | `sidecar/`              | OCR pipeline, `requirements.txt`   |
| Trait data       | `assets/traits.json`    | Extracted trait definitions         |
| Test fixtures    | `fixtures/`             | Screenshot samples for OCR tuning  |
| Design docs      | `docs/`                 | UI spec, design docs, plans        |

## Dev server

```bash
pnpm dev          # Vite dev server on :1420
pnpm tauri dev    # Full Tauri app with hot reload
```

## Frontend type-checking

```bash
pnpm tsc --noEmit
```

## Python sidecar

```bash
cd sidecar
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python process.py <screenshot.png>    # standalone test
```

## Conventions

- Trait slots are hexagon-shaped only (learned traits). Diamond = preference, shield = innate.
- Mentors must be Lv.50+ to appear in the training planner pool.
- Mock roster data in `src/lib/data.ts` — will be replaced by actual OCR captures.
- Screen capture hotkey: Alt+Shift+S (Windows/Linux), registered via `tauri-plugin-global-shortcut`.

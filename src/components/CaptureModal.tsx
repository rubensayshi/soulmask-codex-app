import { useState, useEffect, useCallback, useRef } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'
import { getCurrentWebview } from '@tauri-apps/api/webview'
import { useRosterStore } from '../lib/store'
import type { ProcessResult } from '../lib/types'
import { IcoCamera, IcoExport, IcoX } from './Icons'

interface Props {
  onClose: () => void
  onDone: (action?: 'review') => void
}

const IS_TAURI = '__TAURI_INTERNALS__' in window
const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp']

function isImageFile(name: string): boolean {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  return IMAGE_EXTENSIONS.includes(ext)
}

async function processViaDevServer(files: File[]): Promise<ProcessResult> {
  const paths: string[] = []
  for (const file of files) {
    const buf = await file.arrayBuffer()
    const res = await fetch(`/api/save-temp?name=${encodeURIComponent(file.name)}`, {
      method: 'POST',
      body: buf,
    })
    if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`)
    const { path } = await res.json()
    paths.push(path)
  }

  const res = await fetch('/api/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ paths }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Process failed: ${res.statusText}`)
  }
  return await res.json()
}

export function CaptureModal({ onClose, onDone }: Props) {
  const [phase, setPhase] = useState<'pick' | 'processing' | 'summary'>('pick')
  const [importedCount, setImportedCount] = useState(0)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const processedRef = useRef(false)

  const store = useRosterStore()
  const { captureStatus, lastCaptureCount, captureError, processProgress } = store

  // In Tauri mode, watch store events to transition phases
  useEffect(() => {
    if (!IS_TAURI || phase !== 'processing') return
    if (captureStatus === 'done' && !processedRef.current) {
      processedRef.current = true
      setPhase('summary')
    }
    if (captureStatus === 'error' && captureError) {
      setError(captureError)
      setPhase('pick')
    }
  }, [phase, captureStatus, captureError])

  // Tauri native drag-and-drop (gives file paths directly)
  useEffect(() => {
    if (!IS_TAURI || phase !== 'pick') return
    let cancelled = false
    let unlisten: (() => void) | undefined

    getCurrentWebview().onDragDropEvent((event) => {
      if (cancelled) return
      if (event.payload.type === 'over') {
        setDragOver(true)
      } else if (event.payload.type === 'leave') {
        setDragOver(false)
      } else if (event.payload.type === 'drop') {
        setDragOver(false)
        const paths = event.payload.paths.filter(p => isImageFile(p))
        if (paths.length > 0) startTauriImport(paths)
      }
    }).then(u => { unlisten = u })

    return () => {
      cancelled = true
      unlisten?.()
    }
  }, [phase])

  const startTauriImport = useCallback(async (paths: string[]) => {
    if (paths.length === 0) return
    setImportedCount(paths.length)
    setError(null)
    processedRef.current = false
    setPhase('processing')

    try {
      await invoke('import_images', { paths })
    } catch (e) {
      setError(String(e))
      setPhase('pick')
    }
  }, [])

  const startBrowserImport = useCallback(async (files: File[]) => {
    if (files.length === 0) return
    setImportedCount(files.length)
    setError(null)
    processedRef.current = true
    setPhase('processing')

    try {
      const result = await processViaDevServer(files)
      store.addCaptureResult(result)
      setPhase('summary')
    } catch (e) {
      setError(String(e))
      setPhase('pick')
    }
  }, [store])

  // HTML5 drag-drop handlers (browser mode + prevent Chrome navigation)
  function onDragOver(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    if (!IS_TAURI) setDragOver(true)
  }
  function onDragLeave(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    if (!IS_TAURI) setDragOver(false)
  }
  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
    if (IS_TAURI) return // handled by onDragDropEvent
    const files = Array.from(e.dataTransfer.files).filter(f => isImageFile(f.name))
    if (files.length > 0) startBrowserImport(files)
  }

  async function handlePickImages() {
    if (IS_TAURI) {
      const selected = await open({
        multiple: true,
        filters: [{ name: 'Images', extensions: IMAGE_EXTENSIONS }],
      })
      if (!selected) return
      const paths = Array.isArray(selected) ? selected : [selected]
      if (paths.length > 0) startTauriImport(paths)
    } else {
      const input = document.createElement('input')
      input.type = 'file'
      input.multiple = true
      input.accept = IMAGE_EXTENSIONS.map(e => `.${e}`).join(',')
      input.onchange = () => {
        const files = Array.from(input.files ?? []).filter(f => isImageFile(f.name))
        if (files.length > 0) startBrowserImport(files)
      }
      input.click()
    }
  }

  async function handleCapture() {
    if (!IS_TAURI) return
    setError(null)
    processedRef.current = false
    setImportedCount(1)
    setPhase('processing')

    try {
      const path = await invoke<string>('capture_screen')
      await invoke('import_images', { paths: [path] })
    } catch (e) {
      setError(String(e))
      setPhase('pick')
    }
  }

  const progressParts = processProgress?.split('/') ?? []
  const progressPct = progressParts.length === 2
    ? (parseInt(progressParts[0]) / parseInt(progressParts[1])) * 100
    : null

  const tribesmen = store.tribesmen
  const resultCount = lastCaptureCount ?? 0

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center"
      style={{ background: 'oklch(0.10 0.01 130 / 0.7)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <div
        className="rounded-[var(--radius-lg)] border border-border-soft overflow-hidden"
        style={{ width: 540, background: 'var(--color-bg)', boxShadow: '0 24px 80px oklch(0 0 0 / 0.6)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between" style={{ padding: '16px 22px', borderBottom: '1px solid var(--color-border-soft)' }}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-serif)', fontSize: 22, fontWeight: 600 }}>
            {phase === 'summary'
              ? <>Capture <em style={{ fontStyle: 'italic', color: 'var(--color-accent)', fontWeight: 500 }}>complete</em></>
              : <>Capture <em style={{ fontStyle: 'italic', color: 'var(--color-accent)', fontWeight: 500 }}>roster</em></>}
          </h2>
          <button onClick={onClose} className="grid place-items-center rounded-lg" style={{ width: 36, height: 36, color: 'var(--color-muted)' }}><IcoX /></button>
        </div>

        {/* Pick phase */}
        {phase === 'pick' && (
          <div style={{ padding: '18px 22px 22px' }}>
            <p style={{ margin: '0 0 18px', color: 'var(--color-text-dim)', fontSize: 13 }}>
              Open the in-game tribesman list, then capture. The Python sidecar will detect
              names, levels, clans, classes, titles, and all 366 trait icons.
            </p>

            {error && (
              <div style={{
                margin: '0 0 14px', padding: '10px 14px', fontSize: 12,
                background: 'oklch(0.25 0.06 25)', border: '1px solid oklch(0.40 0.12 25)',
                borderRadius: 'var(--radius)', color: 'oklch(0.80 0.08 25)',
                fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap', maxHeight: 80, overflow: 'auto',
              }}>
                {error}
              </div>
            )}

            <div className="grid gap-3" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: 18 }}>
              <button
                className="btn-primary flex flex-col items-center justify-center gap-2"
                style={{ height: 76, borderRadius: 'var(--radius)' }}
                onClick={handleCapture}
                disabled={!IS_TAURI}
              >
                <IcoCamera size={22} />
                <span>Capture screen</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, color: 'var(--color-muted)', letterSpacing: '0.06em' }}>
                  ALT+SHIFT+S
                </span>
              </button>
              <button
                className="btn-outline flex flex-col items-center justify-center gap-2"
                style={{ height: 76, borderRadius: 'var(--radius)' }}
                onClick={handlePickImages}
              >
                <IcoExport size={20} />
                <span>Import images</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, color: 'var(--color-muted)', letterSpacing: '0.06em' }}>
                  PNG · JPG · WEBP
                </span>
              </button>
            </div>

            <SectionH>Drop zone</SectionH>
            <div
              className="grid place-items-center rounded-[var(--radius)]"
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
              style={{
                padding: '20px 0 18px', marginTop: 10,
                border: `2px dashed ${dragOver ? 'var(--color-accent)' : 'var(--color-border)'}`,
                background: dragOver ? 'oklch(0.18 0.02 160 / 0.3)' : 'oklch(0.14 0.006 130)',
                transition: 'all 0.15s',
              }}
            >
              <div style={{ fontSize: 11.5, color: dragOver ? 'var(--color-accent)' : 'var(--color-muted)' }}>
                {dragOver ? 'Drop images to process' : 'Drag screenshots here'}
              </div>
            </div>

            <div className="flex items-center justify-between" style={{ marginTop: 18 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', letterSpacing: '0.08em' }}>
                ◆ DEDUP ON · MERGE WITH CURRENT ROSTER
              </span>
              <button className="btn-outline" onClick={onClose}>Cancel</button>
            </div>
          </div>
        )}

        {/* Processing phase */}
        {phase === 'processing' && (
          <div style={{ padding: '18px 22px 28px' }}>
            <div className="flex items-center justify-between mb-1">
              <span style={{ fontFamily: 'var(--font-serif)', fontSize: 18, fontStyle: 'italic', color: 'var(--color-accent)' }}>
                Reading the masks…
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-text-dim)' }}>
                {processProgress ?? '…'}
              </span>
            </div>
            <ProgressBar value={progressPct} />

            <div className="grid gap-3.5" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginTop: 24, color: 'var(--color-muted)', fontSize: 11.5 }}>
              <div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, letterSpacing: '0.08em', textTransform: 'uppercase' }}>Screenshots</div>
                <div style={{ fontFamily: 'var(--font-serif)', fontSize: 22, color: 'var(--color-text)' }}>{importedCount}</div>
              </div>
              <div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, letterSpacing: '0.08em', textTransform: 'uppercase' }}>Sidecar</div>
                <div style={{ fontFamily: 'var(--font-serif)', fontSize: 13, color: 'var(--color-text)' }}>OpenCV · Tesseract</div>
              </div>
              <div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, letterSpacing: '0.08em', textTransform: 'uppercase' }}>Status</div>
                <div style={{ fontFamily: 'var(--font-serif)', fontSize: 13, color: 'var(--color-accent)' }}>
                  {captureStatus === 'processing' ? 'Processing…' : IS_TAURI ? captureStatus : 'Processing…'}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Summary phase */}
        {phase === 'summary' && (
          <div style={{ padding: '18px 22px 22px' }}>
            <div
              className="grid gap-4"
              style={{ gridTemplateColumns: 'repeat(2, 1fr)', padding: '18px 0 22px', borderBottom: '1px solid var(--color-border-soft)', marginBottom: 18 }}
            >
              <div>
                <div style={{ fontFamily: 'var(--font-serif)', fontSize: 40, fontWeight: 500 }}>{resultCount}</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  ◆ Cards detected
                </div>
              </div>
              <div>
                <div style={{ fontFamily: 'var(--font-serif)', fontSize: 40, fontWeight: 500, color: 'var(--color-accent)' }}>{tribesmen.length}</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  ◆ Total in roster
                </div>
              </div>
            </div>
            <p style={{ margin: '0 0 18px', color: 'var(--color-text-dim)', fontSize: 13 }}>
              Processed {importedCount} image{importedCount !== 1 ? 's' : ''} and
              found {resultCount} card{resultCount !== 1 ? 's' : ''}.
              Results have been merged into your roster.
            </p>
            <div className="flex justify-end gap-2.5">
              {store.reviewQueue.length > 0 && (
                <button className="btn-primary" onClick={() => onDone('review')}>
                  Review {store.reviewQueue.length} item{store.reviewQueue.length !== 1 ? 's' : ''}
                </button>
              )}
              <button className="btn-outline" onClick={() => onDone()}>Done</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function SectionH({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.12em', color: 'var(--color-muted)', textTransform: 'uppercase' }}>
      {children}
    </div>
  )
}

function ProgressBar({ value }: { value: number | null }) {
  const indeterminate = value === null
  return (
    <div className="rounded-full overflow-hidden" style={{ height: 4, background: 'var(--color-border-soft)' }}>
      <div
        className="h-full rounded-full"
        style={{
          width: indeterminate ? '30%' : value + '%',
          background: 'var(--color-accent)',
          boxShadow: '0 0 8px var(--color-accent-glow)',
          transition: indeterminate ? 'none' : 'width 0.15s ease-out',
          ...(indeterminate ? { animation: 'indeterminate 1.5s ease-in-out infinite' } : {}),
        }}
      />
    </div>
  )
}

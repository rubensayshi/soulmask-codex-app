import type { Plugin } from 'vite'
import { writeFileSync, mkdirSync, rmSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { execFileSync } from 'node:child_process'
import type { IncomingMessage, ServerResponse } from 'node:http'

const TEMP_DIR = join(tmpdir(), 'screenread_dev')

async function readBody(req: IncomingMessage): Promise<Buffer> {
  const chunks: Buffer[] = []
  for await (const chunk of req) chunks.push(chunk as Buffer)
  return Buffer.concat(chunks)
}

export function sidecarPlugin(): Plugin {
  return {
    name: 'sidecar-dev',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((req: IncomingMessage, res: ServerResponse, next: () => void) => {
        const url = new URL(req.url!, `http://${req.headers.host}`)

        if (url.pathname === '/api/save-temp' && req.method === 'POST') {
          handleSaveTemp(req, res, url).catch(err => {
            res.writeHead(500, { 'Content-Type': 'application/json' })
            res.end(JSON.stringify({ error: String(err) }))
          })
          return
        }

        if (url.pathname === '/api/process' && req.method === 'POST') {
          handleProcess(req, res).catch(err => {
            res.writeHead(500, { 'Content-Type': 'application/json' })
            res.end(JSON.stringify({ error: String(err) }))
          })
          return
        }

        next()
      })
    },
  }
}

async function handleSaveTemp(req: IncomingMessage, res: ServerResponse, url: URL) {
  const name = url.searchParams.get('name') || `img_${Date.now()}.png`
  const body = await readBody(req)

  mkdirSync(TEMP_DIR, { recursive: true })
  const path = join(TEMP_DIR, `${Date.now()}_${name}`)
  writeFileSync(path, body)

  res.writeHead(200, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify({ path }))
}

async function handleProcess(req: IncomingMessage, res: ServerResponse) {
  const body = await readBody(req)
  const { paths } = JSON.parse(body.toString()) as { paths: string[] }

  const sidecarDir = join(process.cwd(), 'sidecar')
  const atlasDir = join(process.cwd(), 'assets', 'atlas')
  const processPy = join(sidecarDir, 'process.py')
  const venvPython = join(sidecarDir, '.venv', 'bin', 'python3')
  const python = existsSync(venvPython) ? venvPython : 'python3'

  try {
    const output = execFileSync(python, [processPy, ...paths, '--atlas', atlasDir], {
      cwd: sidecarDir,
      env: { ...process.env, PYTHONPATH: sidecarDir },
      maxBuffer: 50 * 1024 * 1024,
    })

    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(output.toString())
  } finally {
    for (const p of paths) {
      try { rmSync(p) } catch {}
    }
  }
}

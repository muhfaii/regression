import { cp, rm } from 'node:fs/promises'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..', '..')
const DEST = resolve(__dirname, '..', 'src', 'pyodide-src')

const SOURCES = [
  { from: resolve(ROOT, 'backend', 'analysis_modules'), to: resolve(DEST, 'analysis_modules') },
  { from: resolve(ROOT, 'regassist'), to: resolve(DEST, 'regassist') },
]

async function main() {
  await rm(DEST, { recursive: true, force: true })

  for (const { from, to } of SOURCES) {
    await cp(from, to, {
      recursive: true,
      filter: (src) => !src.includes('__pycache__') && (src.endsWith('.py') || src === from),
    })
  }

  console.log('Python sources copied to pyodide-src/')
}

main().catch((err) => {
  console.error('Failed to copy Python sources:', err)
  process.exit(1)
})

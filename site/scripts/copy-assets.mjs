// Copies the report figures and PDFs from ../reports into public/ so the site
// always shows the same images as the reports. public/figures and public/reports
// are generated (git-ignored); run automatically before `dev` and `build`.
import { cpSync, mkdirSync, readdirSync, rmSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repo = join(here, '..', '..')
const pub = join(here, '..', 'public')

// Not published: early screenshot that shows a third-party brand name.
const skip = new Set(['early_web_2.jpeg'])

const figSrc = join(repo, 'reports', 'figures')
const figDst = join(pub, 'figures')
rmSync(figDst, { recursive: true, force: true })
mkdirSync(figDst, { recursive: true })
let n = 0
for (const f of readdirSync(figSrc)) {
  if (skip.has(f)) continue
  cpSync(join(figSrc, f), join(figDst, f))
  n++
}

const repDst = join(pub, 'reports')
rmSync(repDst, { recursive: true, force: true })
mkdirSync(repDst, { recursive: true })
let p = 0
// The PDFs are published in docs/reports (fallback: reports/).
const pdfDir = existsSync(join(repo, 'docs', 'reports')) ? join(repo, 'docs', 'reports') : join(repo, 'reports')
for (const f of readdirSync(pdfDir)) {
  if (f.endsWith('.pdf')) { cpSync(join(pdfDir, f), join(repDst, f)); p++ }
}
if (!existsSync(join(figDst, 'web_operator_route.png'))) throw new Error('figures missing')
console.log(`copied ${n} figures and ${p} reports`)

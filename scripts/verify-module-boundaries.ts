/**
 * Enforce the dependency direction recorded in
 * `.agents/notes/proposed/architecture/2026-11-13-repository-and-runtime-shape.md`:
 * Business calls follow `frontend ─HTTP→ backend ←HTTP─ mcp`; one fixed MCP
 * bootstrap adapter may invoke the installed lifecycle controller.
 *
 * Only directories we own are scanned. The vendored engine and its frontend are
 * exempt by construction: upstream never imports us, and a rule that scans ten
 * thousand upstream files would cost more than the mistake it prevents.
 */

import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'

interface Rule {
  /** Paths under the repository root whose files must obey `forbid`. */
  readonly roots: readonly string[]
  /** Regular expressions matched against each import specifier or import line. */
  readonly forbid: readonly RegExp[]
  /** Explanation printed with every violation. */
  readonly message: string
  /** Paths under a scanned root that may break the rule. */
  readonly allow?: readonly string[]
}

const SOURCE_EXTENSIONS = ['.ts', '.tsx', '.mts', '.cts', '.js', '.jsx', '.mjs', '.cjs', '.vue', '.py']

const IMPORT_PATTERNS = [
  /\bfrom\s+['"]([^'"]+)['"]/g,
  /\bimport\s+['"]([^'"]+)['"]/g,
  /\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
  /\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
]

const PYTHON_FROM_IMPORT = /^[ \t]*from\s+([\w.]+)\s+import\b/gm
const PYTHON_IMPORT = /^[ \t]*import\s+([^\n#]+)/gm

export const RULES: readonly Rule[] = [
  {
    roots: ['src/mcp'],
    forbid: [/workbench\//, /\.\.?\/.*python/],
    message: 'the MCP server reaches business modules over HTTP only; it must not import them',
  },
  {
    roots: ['src/mcp'],
    forbid: [/child_process/],
    message: 'only the fixed lifecycle bootstrap adapter may create a controller process',
    allow: ['src/mcp/src/lifecycle/bootstrap.ts'],
  },
  {
    roots: ['src/workbench/frontend/packages/astrophotoflow-ui'],
    forbid: [
      /^@\/(platform|scripts|stores|services|extensions|composables)(\/|$)/,
      /^src\/(platform|scripts|stores)(\/|$)/,
      /\/src\/(platform|scripts|stores|services|extensions|composables)(\/|$)/,
    ],
    message: 'the UI package takes props and emits events; it must not import host singletons',
  },
  {
    roots: ['src/workbench/frontend/src/platform'],
    forbid: [/workbench\/backend/, /^(astrophotoflow|comfy_api|folder_paths|nodes)\b/],
    message: 'the frontend talks to the backend over HTTP; it must not import backend modules',
  },
  {
    roots: ['src/workbench/backend/astrophotoflow'],
    forbid: [
      /^(comfy|comfy_api|comfy_execution|comfy_extras|nodes|server|folder_paths)\b/,
      /\/(comfy|comfy_api|comfy_execution|comfy_extras|nodes|server|folder_paths)(\/|\.py\b)/,
    ],
    message: 'engine imports belong in interfaces/native/, which is the only module allowed to touch them',
    allow: ['src/workbench/backend/astrophotoflow/interfaces/native'],
  },
]

function* walk(directory: string): Generator<string> {
  for (const entry of readdirSync(directory)) {
    if (entry === 'node_modules' || entry === '__pycache__' || entry === '.git') continue
    const full = join(directory, entry)
    if (statSync(full).isDirectory()) yield* walk(full)
    else if (SOURCE_EXTENSIONS.some(extension => entry.endsWith(extension))) yield full
  }
}

function lineOf(text: string, index: number): number {
  return text.slice(0, index).split('\n').length
}

/** Blank comments without changing line numbers, so examples cannot match. */
function stripComments(text: string): string {
  let result = ''
  let quote: string | undefined
  for (let index = 0; index < text.length; index++) {
    const char = text[index]
    const next = text[index + 1]
    if (quote !== undefined) {
      result += char
      if (char === '\\') {
        result += next ?? ''
        index++
      } else if (char === quote) {
        quote = undefined
      }
      continue
    }
    if (char === '"' || char === "'" || char === '`') {
      quote = char
      result += char
      continue
    }
    if (char === '/' && next === '/') {
      const end = text.indexOf('\n', index)
      const stop = end === -1 ? text.length : end
      result += text.slice(index, stop).replace(/[^\n]/g, ' ')
      index = stop - 1
      continue
    }
    if (char === '/' && next === '*') {
      const end = text.indexOf('*/', index + 2)
      const stop = end === -1 ? text.length : end + 2
      result += text.slice(index, stop).replace(/[^\n]/g, ' ')
      index = stop - 1
      continue
    }
    result += char
  }
  return result
}

function stripHtmlComments(text: string): string {
  return text.replace(/<!--[\s\S]*?-->/g, match => match.replace(/[^\n]/g, ' '))
}

/** Import specifiers in one file, with the line each appears on. */
export function importSpecifiers(path: string, text: string): Array<{ value: string; line: number }> {
  const found: Array<{ value: string; line: number }> = []
  for (const pattern of IMPORT_PATTERNS) {
    pattern.lastIndex = 0
    let match: RegExpExecArray | null
    while ((match = pattern.exec(text)) !== null) found.push({ value: match[1] ?? '', line: lineOf(text, match.index) })
  }
  if (path.endsWith('.py')) {
    PYTHON_FROM_IMPORT.lastIndex = 0
    let match: RegExpExecArray | null
    while ((match = PYTHON_FROM_IMPORT.exec(text)) !== null) {
      found.push({ value: (match[1] ?? '').replace(/^\.+/, ''), line: lineOf(text, match.index) })
    }
    PYTHON_IMPORT.lastIndex = 0
    while ((match = PYTHON_IMPORT.exec(text)) !== null) {
      const line = lineOf(text, match.index)
      for (const item of (match[1] ?? '').split(',')) {
        const name = item.trim().split(/\s+as\s+/)[0]?.trim()
        if (name) found.push({ value: name, line })
      }
    }
  }
  found.sort((a, b) => a.line - b.line)
  return found
}

/** Every violation of `RULES` under `root`, as `path:line: message`. */
export function checkBoundaries(root: string): string[] {
  const violations: string[] = []
  for (const rule of RULES) {
    for (const scanned of rule.roots) {
      const start = resolve(root, scanned)
      if (!existsSync(start)) continue
      const allowed = (rule.allow ?? []).map(path => resolve(root, path))
      for (const file of walk(start)) {
        if (allowed.some(path => file === path || file.startsWith(`${path}/`))) continue
        const raw = readFileSync(file, 'utf8')
        const text = stripComments(
          file.endsWith('.vue') ? stripHtmlComments(raw) : raw
        )
        for (const { value, line } of importSpecifiers(file, text)) {
          const candidates = [value]
          if (value.startsWith('.')) {
            candidates.push(
              relative(root, resolve(dirname(file), value)).split('\\').join('/')
            )
          }
          const hit = rule.forbid.find(pattern =>
            candidates.some(candidate => pattern.test(candidate))
          )
          if (hit === undefined) continue
          violations.push(`${relative(root, file).split('\\').join('/')}:${line}: imports '${value}' — ${rule.message}`)
          break
        }
      }
    }
  }
  return violations
}

if (import.meta.main) {
  const root = resolve(import.meta.dirname, '..')
  const violations = checkBoundaries(root)
  if (violations.length > 0) {
    console.error('verify-module-boundaries failed:\n')
    for (const violation of violations) console.error(`  ${violation}`)
    console.error('\nSee .agents/notes/proposed/architecture/2026-11-13-repository-and-runtime-shape.md.')
    process.exit(1)
  }
  console.log(`verify-module-boundaries: ${RULES.length} rules, no violations.`)
}

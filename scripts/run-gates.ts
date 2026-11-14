/**
 * Run the repository's quality gates in one aggregate.
 *
 * `quick` covers the documentation and Agent Note gates; `full` adds the type
 * check and the unit tests. Package scripts own the public names (`check`,
 * `check:full`), so a CI job only has to call one of them. Every gate runs as
 * its own process, all selected gates run even after a failure, and the summary
 * names what failed so one red gate does not hide another.
 */

import { spawnSync } from 'node:child_process'
import { performance } from 'node:perf_hooks'

type Mode = 'quick' | 'full'

interface Gate {
  /** Stable identifier used in the summary and in failure reporting. */
  id: string
  /** Modes that include this gate. */
  modes: Mode[]
  command: string
  args: string[]
}

const GATES: Gate[] = [
  { id: 'typecheck', modes: ['full'], command: 'pnpm', args: ['exec', 'tsc', '--noEmit'] },
  { id: 'unit', modes: ['full'], command: 'pnpm', args: ['exec', 'vitest', 'run'] },
  { id: 'module-boundaries', modes: ['quick', 'full'], command: 'node', args: ['scripts/verify-module-boundaries.ts'] },
  {
    id: 'agent-note-classification',
    modes: ['quick', 'full'],
    command: 'node',
    args: ['scripts/verify-agent-note-classification.ts'],
  },
  { id: 'agent-note-format', modes: ['quick', 'full'], command: 'node', args: ['scripts/verify-agent-note-format.ts'] },
  { id: 'agent-note-archive', modes: ['quick', 'full'], command: 'node', args: ['scripts/verify-archived-agent-notes.ts'] },
  { id: 'doc-budgets', modes: ['quick', 'full'], command: 'node', args: ['scripts/verify-doc-budgets.ts'] },
  { id: 'translation-pairing', modes: ['quick', 'full'], command: 'node', args: ['scripts/verify-translation-pairing.ts'] },
  { id: 'translation-prompt', modes: ['quick', 'full'], command: 'node', args: ['scripts/verify-translation-prompt.ts'] },
]

const argv = process.argv.slice(2)
if (argv.includes('--list')) {
  for (const gate of GATES) console.log(`${gate.modes.join(',').padEnd(12)} ${gate.id}`)
  process.exit(0)
}

const mode = argv[0] as Mode | undefined
if (mode !== 'quick' && mode !== 'full') {
  console.error('run-gates: usage: run-gates.ts <quick|full> [--list]')
  process.exit(2)
}

const selected = GATES.filter(gate => gate.modes.includes(mode))
const failed: string[] = []
const started = performance.now()

for (const gate of selected) {
  const gateStart = performance.now()
  const result = spawnSync(gate.command, gate.args, { stdio: ['ignore', 'inherit', 'inherit'], shell: false })
  const seconds = ((performance.now() - gateStart) / 1000).toFixed(1)
  if (result.error !== undefined) {
    failed.push(`${gate.id} (${result.error.message})`)
    console.error(`✖ ${gate.id} ${seconds}s`)
  } else if (result.status !== 0) {
    failed.push(`${gate.id} (exit ${String(result.status)})`)
    console.error(`✖ ${gate.id} ${seconds}s`)
  } else {
    console.log(`✔ ${gate.id} ${seconds}s`)
  }
}

const total = ((performance.now() - started) / 1000).toFixed(1)
if (failed.length > 0) {
  console.error(`\ngates [${mode}]: ${failed.length} of ${selected.length} failed in ${total}s\n`)
  for (const failure of failed) console.error(`  ${failure}`)
  process.exit(1)
}
console.log(`\ngates [${mode}]: ${selected.length} passed in ${total}s`)

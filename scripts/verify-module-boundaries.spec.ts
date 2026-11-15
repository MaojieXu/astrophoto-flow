import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'

import { checkBoundaries, importSpecifiers } from './verify-module-boundaries.ts'

const created: string[] = []

function fixture(files: Record<string, string>): string {
  const root = mkdtempSync(join(tmpdir(), 'apf-boundaries-'))
  created.push(root)
  for (const [path, contents] of Object.entries(files)) {
    const full = join(root, path)
    mkdirSync(join(full, '..'), { recursive: true })
    writeFileSync(full, contents)
  }
  return root
}

afterEach(() => {
  while (created.length > 0) rmSync(created.pop()!, { recursive: true, force: true })
})

describe('checkBoundaries', () => {
  it('accepts a tree whose owned directories do not cross a rule', () => {
    const root = fixture({
      'src/mcp/src/index.ts': "import { FastMCP } from 'fastmcp'\n",
      'src/workbench/frontend/packages/astrophotoflow-ui/A.vue': "import { defineComponent } from 'vue'\n",
      'src/workbench/frontend/src/platform/astrophotoflow/api.ts': "fetch('/api/v1/assets')\n",
    })
    expect(checkBoundaries(root)).toEqual([])
  })

  it('rejects the MCP server importing the workbench', () => {
    const root = fixture({
      'src/mcp/src/index.ts': "import { runtime } from '../../workbench/backend/runtime.ts'\n",
    })
    const violations = checkBoundaries(root)
    expect(violations).toHaveLength(1)
    expect(violations[0]).toContain('src/mcp/src/index.ts:1')
    expect(violations[0]).toContain('over HTTP only')
  })

  it('rejects the UI package importing a host singleton', () => {
    const root = fixture({
      'src/workbench/frontend/packages/astrophotoflow-ui/Asset.vue': "import { api } from '@/scripts/api'\n",
    })
    const violations = checkBoundaries(root)
    expect(violations).toHaveLength(1)
    expect(violations[0]).toContain('host singletons')
  })

  it('resolves a relative import to the host singleton it reaches', () => {
    const root = fixture({
      'src/workbench/frontend/packages/astrophotoflow-ui/Asset.vue':
        "import { api } from '../../src/scripts/api'\n",
    })
    const violations = checkBoundaries(root)
    expect(violations).toHaveLength(1)
    expect(violations[0]).toContain('host singletons')
  })

  it('rejects a bare relative import of a host directory', () => {
    const root = fixture({
      'src/workbench/frontend/packages/astrophotoflow-ui/Asset.vue':
        "import { useStore } from '../../src/stores'\n",
    })
    const violations = checkBoundaries(root)
    expect(violations).toHaveLength(1)
    expect(violations[0]).toContain('host singletons')
  })

  it('scans .cts modules for child_process imports', () => {
    const root = fixture({
      'src/mcp/index.cts': "import { spawn } from 'node:child_process'\n",
    })
    const violations = checkBoundaries(root)
    expect(violations).toHaveLength(1)
    expect(violations[0]).toContain('fixed lifecycle bootstrap')
  })

  it('permits process creation only in the fixed bootstrap adapter', () => {
    const root = fixture({
      'src/mcp/src/lifecycle/bootstrap.ts': "import { execFile } from 'node:child_process'\n",
      'src/mcp/src/status.ts': "import { execFile } from 'node:child_process'\n",
    })
    const violations = checkBoundaries(root)
    expect(violations).toHaveLength(1)
    expect(violations[0]).toContain('src/mcp/src/status.ts:1')
  })

  it('does not let the bootstrap exception import backend code', () => {
    const root = fixture({
      'src/mcp/src/lifecycle/bootstrap.ts': "import { runtime } from '../../../workbench/backend/runtime.ts'\n",
    })
    expect(checkBoundaries(root)[0]).toContain('must not import')
  })

  it('ignores imports written inside Vue comments', () => {
    const root = fixture({
      'src/workbench/frontend/packages/astrophotoflow-ui/Asset.vue':
        "<!-- import { api } from '@/scripts/api' -->\n// import { api } from '@/scripts/api'\n<script setup lang=\"ts\">\nimport { defineComponent } from 'vue'\n</script>\n",
    })
    expect(checkBoundaries(root)).toEqual([])
  })

  it('rejects the platform layer importing a backend module', () => {
    const root = fixture({
      'src/workbench/frontend/src/platform/astrophotoflow/socket.ts': "import { load } from 'comfy_api'\n",
    })
    expect(checkBoundaries(root)[0]).toContain('must not import backend modules')
  })

  it('lets interfaces/native import the engine and nothing else do so', () => {
    const root = fixture({
      'src/workbench/backend/astrophotoflow/interfaces/native/canvas.py': 'from comfy_api import io\n',
      'src/workbench/backend/astrophotoflow/core/clock.py': 'import comfy_api\n',
    })
    const violations = checkBoundaries(root)
    expect(violations).toHaveLength(1)
    expect(violations[0]).toContain('astrophotoflow/core/clock.py:1')
  })

  it('checks every name in a multi-name Python import', () => {
    const root = fixture({
      'src/workbench/backend/astrophotoflow/core/clock.py': 'import os, comfy\n',
    })
    const violations = checkBoundaries(root)
    expect(violations).toHaveLength(1)
    expect(violations[0]).toContain('astrophotoflow/core/clock.py:1')
  })
})

describe('importSpecifiers', () => {
  it('reports the line of every import, in both languages', () => {
    const text = "import a from 'one'\n\nexport const x = await import('two')\n"
    expect(importSpecifiers('x.ts', text)).toEqual([
      { value: 'one', line: 1 },
      { value: 'two', line: 3 },
    ])
    const python = 'import os, comfy\n\nfrom ..core import clock\n'
    expect(importSpecifiers('x.py', python)).toEqual([
      { value: 'os', line: 1 },
      { value: 'comfy', line: 1 },
      { value: 'core', line: 3 },
    ])
  })
})

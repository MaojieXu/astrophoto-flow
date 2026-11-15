// Export the FastAPI OpenAPI snapshot the MCP client is generated from.
// The snapshot lives in docs/api/openapi.json and is never edited by hand.
import { spawnSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const backend = join(repoRoot, 'src', 'workbench', 'backend');
const output = resolve(repoRoot, 'docs', 'api', 'openapi.json');

mkdirSync(dirname(output), { recursive: true });
const result = spawnSync(
  'uv',
  [
    'run',
    '--locked',
    '--no-sync',
    '--project',
    backend,
    'python',
    '-m',
    'astrophotoflow.export_openapi',
    output,
  ],
  {
    cwd: backend,
    env: { ...process.env, PYTHONPATH: backend, PYTHONUTF8: '1' },
    encoding: 'utf8',
    stdio: 'inherit',
  },
);
process.exit(result.status ?? 1);

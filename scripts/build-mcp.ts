import { cpSync, readFileSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const directory = resolve(root, 'src/mcp')
const product = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8')) as { version: string }
rmSync(resolve(directory, 'dist'), { recursive: true, force: true })
const result = spawnSync(process.execPath, [resolve(directory, 'node_modules/typescript/bin/tsc'), '-p', directory], { stdio: 'inherit' })
if (result.error) throw result.error
if (result.status !== 0) process.exit(result.status ?? 1)
cpSync(resolve(directory, 'installer'), resolve(directory, 'dist/installer'), { recursive: true })
console.log(`Built MCP ${product.version}`)

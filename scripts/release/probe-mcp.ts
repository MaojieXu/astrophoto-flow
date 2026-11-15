import { createServer } from 'node:http'
import { createHash } from 'node:crypto'
import { existsSync } from 'node:fs'
import { readFile, stat } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

/**
 * Drive the packaged MCP over stdio and prove the whole lifecycle is real.
 *
 * The script only uses public tool calls plus HTTP reads of the URLs the tools
 * return; it never reaches into the workspace files to fake a state.
 */

interface ProbeScenario {
  version: string
  workspace: string
  installRoot: string
  webIndexSha256: string
  mcp: { command: string; args: string[] }
  expectNotInstalled: boolean
  occupiedPorts: number[]
}

const scenarioPath = process.argv[2]
if (!scenarioPath) throw new Error('Supply a scenario JSON path.')
const scenario = JSON.parse(await readFile(scenarioPath, 'utf8')) as ProbeScenario
/** Resolve the MCP client next to the installed package; its exports are ESM only. */
function resolveClientModule(entry: string): string {
  const candidates = [
    join(dirname(entry), '../../../@prefecthq/fastmcp-ts/dist/client.js'),
    join(dirname(entry), '../node_modules/@prefecthq/fastmcp-ts/dist/client.js'),
  ]
  const found = candidates.find(candidate => existsSync(candidate))
  if (!found) throw new Error(`Cannot find the fastmcp-ts client module next to ${entry}.`)
  return found
}

interface ProbeClient {
  callTool(
    name: string,
    args: Record<string, unknown>,
    options?: { timeout: number },
  ): Promise<{ isError?: boolean; content: { text?: string }[]; structuredContent?: unknown }>
  listTools(): Promise<{ name: string }[]>
  close(): Promise<void>
}

interface ClientModule {
  Client: { connect(transport: unknown): Promise<ProbeClient> }
  StdioTransport: new (command: string, args: string[]) => unknown
}

const { Client, StdioTransport } = (await import(
  pathToFileURL(resolveClientModule(scenario.mcp.args[0] ?? scenario.mcp.command)).href
)) as ClientModule

const occupied = (scenario.occupiedPorts.length ? scenario.occupiedPorts : [8188, 8190]).map(port => {
  const server = createServer((_, response) => {
    response.end('occupied acceptance port')
  })
  return { server, port }
})

const checks: string[] = []
let client: ProbeClient | undefined

function check(name: string, condition: boolean, detail: string): void {
  if (!condition) throw new Error(`${name}: ${detail}`)
  checks.push(name)
}

async function structured<T>(name: string, args: Record<string, unknown> = {}, timeout = 900): Promise<T> {
  const result = await client!.callTool(name, args, { timeout })
  if (result.isError) throw new Error(`${name} failed: ${result.content.map(item => ('text' in item ? item.text : '')).join(' ')}`)
  return (result.structuredContent ?? {}) as T
}

async function pageHash(url: string): Promise<string> {
  const response = await fetch(url, { signal: AbortSignal.timeout(15_000), redirect: 'error' })
  if (!response.ok) throw new Error(`GET ${url} answered ${response.status}.`)
  return createHash('sha256').update(Buffer.from(await response.arrayBuffer())).digest('hex')
}

async function unreachable(url: string): Promise<boolean> {
  try {
    await fetch(url, { signal: AbortSignal.timeout(2_000), redirect: 'error' })
    return false
  } catch {
    return true
  }
}

try {
  for (const { server, port } of occupied) {
    await new Promise<void>((done, fail) => {
      server.once('error', fail)
      server.listen(port, '127.0.0.1', done)
    })
  }

  client = await Client.connect(new StdioTransport(scenario.mcp.command, scenario.mcp.args))

  const tools = (await client.listTools()).map(tool => tool.name).sort()
  const expectedTools = ['nodes_find', 'nodes_get', 'workbench_init', 'workbench_start', 'workbench_status', 'workbench_stop']
  check('tool-surface', JSON.stringify(tools) === JSON.stringify(expectedTools), `tools were ${tools.join(', ')}`)

  // The schema refuses unknown input either as a tool error or as a protocol
  // error; both outcomes prove no caller value reaches a command line.
  let arbitraryRejected = false
  try {
    const arbitrary = await client.callTool('workbench_start', { command: 'not-an-allowed-input' })
    arbitraryRejected = arbitrary.isError === true
  } catch {
    arbitraryRejected = true
  }
  check('arbitrary-argument-rejected', arbitraryRejected, 'workbench_start accepted an unknown command argument')

  const statusBefore = await structured<{ status: string }>('workbench_status')
  if (scenario.expectNotInstalled) {
    check('status-before-init', statusBefore.status === 'not_installed', `status was ${statusBefore.status}`)
  }

  const init = await structured<{ status: string; operation_id?: string | null; version?: string }>('workbench_init')
  // Installation continues independently when the MCP transport closes.
  if (scenario.expectNotInstalled && (init.status === 'accepted' || init.status === 'running')) {
    await client.close()
    client = undefined
    await new Promise(resolve => setTimeout(resolve, 2_000))
    client = await Client.connect(new StdioTransport(scenario.mcp.command, scenario.mcp.args))
  }
  let initState = (await structured<{ status: string }>('workbench_status')).status
  const initDeadline = Date.now() + 20 * 60_000
  while (initState === 'installing') {
    if (Date.now() > initDeadline) throw new Error('workbench_init did not finish in 20 minutes.')
    await new Promise(resolve => setTimeout(resolve, 2_000))
    initState = (await structured<{ status: string }>('workbench_status')).status
    if (initState === 'install_failed') throw new Error('workbench_init reported install_failed; see the install log.')
  }
  check('init-completed', initState === 'stopped' || initState === 'ready', `status after init was ${initState}`)
  if (scenario.expectNotInstalled) checks.push('install-survives-mcp')
  const installReceipt = JSON.parse(await readFile(join(scenario.installRoot, 'installation.json'), 'utf8'))
  check('install-receipt', installReceipt.version === scenario.version, `receipt version was ${installReceipt.version}`)

  const first = await structured<{ status: string; version: string; workspace: string; service_url: string; web_url: string; reused: boolean; verified: boolean }>('workbench_start')
  check('start-ready', first.status === 'ready' && first.verified === true, 'workbench_start did not verify the pair')
  check('start-identity', first.version === scenario.version && resolve(first.workspace).toLowerCase() === resolve(scenario.workspace).toLowerCase(), 'start returned another installation')
  const occupiedPorts = new Set(occupied.map(entry => entry.port))
  const usedPorts = [first.service_url, first.web_url].map(url => Number(new URL(url).port))
  check('port-conflict-avoided', usedPorts.every(port => !occupiedPorts.has(port)), `controller used occupied port(s) ${usedPorts.join(', ')}`)
  check('packaged-frontend', (await pageHash(first.web_url)) === scenario.webIndexSha256, 'the served page is not the packaged index.html')

  const page = await structured<{ items: Array<{ node_type: string; display_name: string }>; total: number; next_cursor?: string | null }>('nodes_find', { limit: 5 })
  check('nodes-find', page.total > 0 && page.items.length > 0, 'nodes_find returned no native nodes')
  const definition = await structured<{ node_type: string; definition: Record<string, unknown> }>('nodes_get', { node_type: page.items[0].node_type })
  check('nodes-get', definition.node_type === page.items[0].node_type && typeof definition.definition === 'object', 'nodes_get returned another definition')

  const second = await structured<{ web_url: string; reused: boolean }>('workbench_start')
  check('start-reused', second.reused === true && second.web_url === first.web_url, 'a repeated start did not reuse the running pair')

  await client.close()
  client = undefined
  check('web-survives-mcp', (await pageHash(first.web_url)) === scenario.webIndexSha256, 'the canvas stopped being served after the MCP disconnected')

  client = await Client.connect(new StdioTransport(scenario.mcp.command, scenario.mcp.args))
  const stopped = await structured<{ status: string; verified: boolean }>('workbench_stop')
  check('stop-completed', stopped.status === 'stopped' && stopped.verified === true, `stop reported ${stopped.status}`)
  check('stop-ports-closed', (await unreachable(first.service_url)) && (await unreachable(first.web_url)), 'a port still answers after stop')

  const afterStop = await structured<{ status: string; workspace: string }>('workbench_status')
  check('status-after-stop', afterStop.status === 'stopped', `status after stop was ${afterStop.status}`)
  check('workspace-preserved', (await stat(join(scenario.workspace, 'config.toml'))).size > 0 && (await stat(join(scenario.workspace, 'data', 'workbench.sqlite3'))).size > 0, 'the workspace lost its configuration or database')

  const restarted = await structured<{ status: string; web_url: string; reused: boolean }>('workbench_start')
  check('restart-after-stop', restarted.status === 'ready' && restarted.reused === false, 'a start after stop did not bring up a fresh pair')
  check('restart-frontend', (await pageHash(restarted.web_url)) === scenario.webIndexSha256, 'the restarted workbench serves another page')

  const finalStop = await structured<{ status: string }>('workbench_stop')
  check('shutdown-controlled', finalStop.status === 'stopped', `final stop reported ${finalStop.status}`)

  console.log(JSON.stringify({ status: 'passed', version: scenario.version, workspace: scenario.workspace, web_url: restarted.web_url, checks }))
} finally {
  await client?.close()
  for (const { server } of occupied) await new Promise<void>(done => server.close(() => done()))
}

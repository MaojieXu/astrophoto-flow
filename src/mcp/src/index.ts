#!/usr/bin/env node
import { FastMCP } from '@prefecthq/fastmcp-ts/server';

import { registerNodeTools } from './api/nodes.js';
import { parseConfiguration } from './config.js';
import { readProductVersion } from './lifecycle/bootstrap.js';
import { registerLifecycleTools } from './lifecycle/tools.js';

const INSTRUCTIONS = [
  'This server owns one local AstroPhotoFlow workbench workspace.',
  'Call workbench_init once to install or adopt the matching version, then poll workbench_status until it is no longer installing.',
  'workbench_start returns the local web_url of the running native canvas; open that URL to draw graphs, and let ComfyUI keep ownership of graphs, drafts, queue and execution.',
  'nodes_find and nodes_get read the engine catalog through the local service and require a started workbench.',
  'workbench_stop stops only the processes this workspace owns and keeps installation, configuration, database, assets and workflows.',
].join(' ');

async function main(): Promise<void> {
  let configuration;
  try {
    configuration = parseConfiguration(process.argv.slice(2));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`AstroPhotoFlow MCP configuration error: ${message}`);
    process.exit(2);
  }
  const version = await readProductVersion();
  const server = new FastMCP({ name: 'AstroPhotoFlow', version, instructions: INSTRUCTIONS });
  registerLifecycleTools(server, configuration);
  registerNodeTools(server, configuration);
  await server.run();
}

await main();

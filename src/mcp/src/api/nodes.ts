import type { FastMCP } from '@prefecthq/fastmcp-ts/server';
import { z } from 'zod';

import type { Configuration } from '../config.js';
import { zNodeDefinition, zNodePage } from '../generated/api/zod.gen.js';
import { findNodes, getNode } from '../generated/api/sdk.gen.js';
import { guard } from '../guard.js';
import { openWorkbenchApi } from './client.js';
import { serviceFailure } from './errors.js';

const findInput = z.strictObject({
  query: z.string().min(1).max(200).optional(),
  cursor: z.string().min(1).max(32).optional(),
  limit: z.number().int().min(1).max(200).optional(),
});

const getInput = z.strictObject({
  node_type: z.string().min(1).max(200),
});

/**
 * Register the read-only node tools.
 *
 * Both tools go through the local service, which owns the engine connection:
 * the MCP never talks to ComfyUI directly or reads the engine's catalog files.
 */
export function registerNodeTools(server: FastMCP, config: Configuration): void {
  server.tool(
    {
      name: 'nodes_find',
      title: 'Find native ComfyUI nodes',
      description:
        'Page through the native node catalog of the running workbench. Filter with one case-insensitive query over node type, display name and category. Requires a started workbench.',
      input: findInput,
    },
    (args) =>
      guard(async () => {
        const input = findInput.parse(args);
        const { client } = await openWorkbenchApi(config);
        const { data, error } = await findNodes({
          client,
          query: { query: input.query, cursor: input.cursor, limit: input.limit },
        });
        if (error || !data) {
          throw serviceFailure(error, 'NODES_UNAVAILABLE', 'The workbench did not return a node page.');
        }
        return zNodePage.parse(data);
      }),
  );

  server.tool(
    {
      name: 'nodes_get',
      title: 'Get one native ComfyUI node',
      description:
        'Return the running engine\'s own definition for exactly one node type, including inputs, outputs and category. Requires a started workbench.',
      input: getInput,
    },
    (args) =>
      guard(async () => {
        const input = getInput.parse(args);
        const { client } = await openWorkbenchApi(config);
        const { data, error } = await getNode({ client, path: { node_type: input.node_type } });
        if (error || !data) {
          throw serviceFailure(error, 'NODE_NOT_FOUND', `The engine has no node type named ${input.node_type}.`);
        }
        return zNodeDefinition.parse(data);
      }),
  );
}

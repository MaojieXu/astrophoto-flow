import type { ComfyWorkflowJSON } from '@/platform/workflow/validation/schemas/workflowSchema'

export const blankGraph: ComfyWorkflowJSON = {
  last_node_id: 0,
  last_link_id: 0,
  nodes: [],
  links: [],
  groups: [],
  config: {},
  extra: {},
  version: 0.4
}

export const defaultGraph: ComfyWorkflowJSON = {
  last_node_id: 1,
  last_link_id: 0,
  nodes: [
    {
      id: 1,
      type: 'EmptyImage',
      pos: [100, 100],
      size: [315, 106],
      flags: {},
      order: 0,
      mode: 0,
      inputs: [],
      outputs: [
        { name: 'IMAGE', type: 'IMAGE', links: null, slot_index: 0 }
      ],
      properties: { 'Node name for S&R': 'EmptyImage' },
      widgets_values: [512, 512, 1, 0]
    }
  ],
  links: [],
  groups: [],
  config: {},
  extra: {},
  version: 0.4
}

export const defaultGraphJSON = JSON.stringify(defaultGraph)

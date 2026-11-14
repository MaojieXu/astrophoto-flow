import type { Ref } from 'vue'

import { useSharedCanvasPositionConversion } from '@/composables/element/useCanvasPositionConversion'
import { usePragmaticDroppable } from '@/composables/usePragmaticDragAndDrop'
import type { Point } from '@/lib/litegraph/src/litegraph'
import { LiteGraph } from '@/lib/litegraph/src/litegraph'
import { withNodeAddSource } from '@/platform/telemetry/nodeAdded/nodeAddSource'
import { useWorkflowService } from '@/platform/workflow/core/services/workflowService'
import { ComfyWorkflow } from '@/platform/workflow/management/stores/workflowStore'
import { app as comfyApp } from '@/scripts/app'
import { useLitegraphService } from '@/services/litegraphService'
import { ComfyNodeDefImpl } from '@/stores/nodeDefStore'
import type { RenderedTreeExplorerNode } from '@/types/treeExplorerTypes'
import { isSelectOnly } from '@/utils/litegraphUtil'

export const useCanvasDrop = (dropTargetRef: Ref<HTMLElement | null>) => {
  const litegraphService = useLitegraphService()
  const workflowService = useWorkflowService()

  usePragmaticDroppable(() => dropTargetRef.value, {
    getDropEffect: (args): Exclude<DataTransfer['dropEffect'], 'none'> =>
      args.source.data.type === 'tree-explorer-node' ? 'copy' : 'move',
    onDrop: async (event) => {
      if (isSelectOnly(comfyApp.canvas)) return
      const loc = event.location.current.input
      const dndData = event.source.data

      if (dndData.type === 'tree-explorer-node') {
        const node = dndData.data as RenderedTreeExplorerNode
        const conv = useSharedCanvasPositionConversion()
        const basePos = conv.clientPosToCanvasPos([loc.clientX, loc.clientY])

        if (node.data instanceof ComfyNodeDefImpl) {
          const nodeDef = node.data
          const pos: Point = [...basePos]
          // Add an offset on y to make sure after adding the node, the cursor
          // is on the node (top left corner)
          pos[1] += LiteGraph.NODE_TITLE_HEIGHT
          withNodeAddSource('sidebar_drag', () =>
            litegraphService.addNodeOnGraph(nodeDef, { pos })
          )
        } else if (node.data instanceof ComfyWorkflow) {
          const workflow = node.data
          await workflowService.insertWorkflow(workflow, { position: basePos })
        }
      }
    }
  })
}

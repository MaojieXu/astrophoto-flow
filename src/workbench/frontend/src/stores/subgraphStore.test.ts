import { fromPartial } from '@total-typescript/shoehorn'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

vi.mock(import('@vueuse/router'), () => ({ useRouteHash: () => ref('') }))

import {
  createTestSubgraph,
  createTestSubgraphNode
} from '@/lib/litegraph/src/subgraph/__fixtures__/subgraphHelpers'
import type { ExportedSubgraph } from '@/lib/litegraph/src/types/serialisation'
import type { ComfyNodeDef as ComfyNodeDefV1 } from '@/schemas/nodeDefSchema'
import { api } from '@/scripts/api'
import { app as comfyApp } from '@/scripts/app'
import { useDialogService } from '@/services/dialogService'
import { useLitegraphService } from '@/services/litegraphService'
import { useNodeDefStore } from '@/stores/nodeDefStore'
import { useSubgraphStore } from '@/stores/subgraphStore'
import { useCanvasStore } from '@/renderer/core/canvas/canvasStore'
import { BLUEPRINT_TYPE_PREFIX } from '@/utils/blueprintUtils'

vi.mock(import('@/platform/telemetry'))

// Add mock for api at the top of the file
vi.mock<unknown>(import('@/scripts/api'), () => ({
  api: {
    getUserData: vi.fn(),
    storeUserData: vi.fn(),
    listUserDataFullInfo: vi.fn(),
    deleteUserData: vi.fn(() =>
      Promise.resolve(new Response(null, { status: 204 }))
    ),
    apiURL: vi.fn(),
    addEventListener: vi.fn()
  }
}))
vi.mock(import('@/services/dialogService'))

vi.mock<unknown>(import('@/scripts/app'), () => ({
  app: {
    canvas: {
      _deserializeItems: vi.fn((i) => i),
      ds: { visible_area: [0, 0, 0, 0] },
      selected_nodes: null
    },
    loadGraphData: vi.fn()
  }
}))

const mockGraph = {
  nodes: [{ type: '123' }],
  definitions: { subgraphs: [{ id: '123' }] }
}

describe('useSubgraphStore', () => {
  let store: ReturnType<typeof useSubgraphStore>
  async function mockFetch(filenames: Record<string, unknown>) {
    vi.mocked(api.listUserDataFullInfo).mockResolvedValue(
      Object.keys(filenames).map((filename) => ({
        path: filename,
        modified: new Date().getTime(),
        size: 1 // size !== -1 for remote workflows
      }))
    )
    vi.mocked(api).getUserData = vi.fn((f) =>
      Promise.resolve({
        status: 200,
        text: () => Promise.resolve(JSON.stringify(filenames[f.slice(10)]))
      } as Response)
    )
    return await store.fetchSubgraphs()
  }

  function userBlueprintNames() {
    return useNodeDefStore()
      .nodeDefs.filter((d) => d.category === 'Subgraph Blueprints/User')
      .map((d) => d.name)
  }

  beforeEach(() => {
    vi.mocked(useDialogService().prompt).mockResolvedValue('testname')
    vi.mocked(useDialogService().confirm).mockResolvedValue(true)
    vi.mocked(useCanvasStore().getCanvas).mockImplementation(
      () => comfyApp.canvas
    )
    store = useSubgraphStore()
  })

  function selectSubgraphNodeToPublish() {
    const subgraph = createTestSubgraph()
    const subgraphNode = createTestSubgraphNode(subgraph)
    const graph = subgraphNode.graph!
    graph.add(subgraphNode)
    vi.mocked(comfyApp.canvas).selectedItems = new Set([subgraphNode])
    vi.mocked(comfyApp.canvas)._serializeItems = vi.fn(() => {
      const serializedSubgraph = fromPartial<ExportedSubgraph>({
        ...subgraph.serialize(),
        links: [],
        groups: [],
        version: 1
      })
      return {
        nodes: [subgraphNode.serialize()],
        subgraphs: [serializedSubgraph]
      }
    })
    //mock saving of file
    vi.mocked(api.storeUserData).mockResolvedValue({
      status: 200,
      json: () =>
        Promise.resolve({
          path: 'subgraphs/testname.json',
          modified: Date.now(),
          size: 2
        })
    } as Response)
  }

  it.for([
    { confirmed: true, storeCalls: 1 },
    { confirmed: false, storeCalls: 0 }
  ])(
    'should publish over an existing blueprint only when overwrite is confirmed (confirmed: $confirmed)',
    async ({ confirmed, storeCalls }) => {
      selectSubgraphNodeToPublish()
      vi.mocked(useDialogService().confirm).mockResolvedValue(confirmed)
      await mockFetch({ 'testname.json': mockGraph })
      await store.publishSubgraph()
      expect(useDialogService().confirm).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'overwriteBlueprint',
          itemList: ['testname']
        })
      )
      expect(api.storeUserData).toHaveBeenCalledTimes(storeCalls)
    }
  )
  it('should display published nodes in the node library', async () => {
    await mockFetch({ 'test.json': mockGraph })
    expect(userBlueprintNames()).toEqual(['SubgraphBlueprint.test'])
  })
  it('should remove deleted blueprints from the node library', async () => {
    await mockFetch({ 'test.json': mockGraph })
    await store.deleteBlueprint('SubgraphBlueprint.test')
    expect(api.deleteUserData).toHaveBeenCalledWith('subgraphs/test.json')
    expect(userBlueprintNames()).toEqual([])
  })
  it('should allow subgraphs to be edited', async () => {
    await mockFetch({ 'test.json': mockGraph })
    await store.editBlueprint(BLUEPRINT_TYPE_PREFIX + 'test')
    //check active graph
    expect(comfyApp.loadGraphData).toHaveBeenCalled()
  })
  it('should allow subgraphs to be added to graph', async () => {
    //mock
    await mockFetch({ 'test.json': mockGraph })
    const res = useLitegraphService().addNodeOnGraph({
      name: 'SubgraphBlueprint.test'
    } as ComfyNodeDefV1)
    expect(res).toBeTruthy()
  })
  it('should return a deep copy from getBlueprint so mutations do not corrupt the cache', async () => {
    await mockFetch({ 'test.json': mockGraph })
    const first = store.getBlueprint(BLUEPRINT_TYPE_PREFIX + 'test')
    first.nodes[0].id = -1
    first.definitions!.subgraphs[0].id = 'corrupted'

    const second = store.getBlueprint(BLUEPRINT_TYPE_PREFIX + 'test')
    expect(second.nodes[0].id).not.toBe(-1)
    expect(second.definitions!.subgraphs[0].id).toBe('123')
  })
  describe('isUserBlueprint', () => {
    it('should return true for user blueprints', async () => {
      await mockFetch({ 'test.json': mockGraph })
      expect(store.isUserBlueprint('SubgraphBlueprint.test')).toBe(true)
    })

    it('should return false for non-blueprint node types', () => {
      expect(store.isUserBlueprint('KSampler')).toBe(false)
    })

    it('should return false for undefined', () => {
      expect(store.isUserBlueprint(undefined)).toBe(false)
    })
  })

  describe('search_aliases support', () => {
    it('should include search_aliases from workflow extra', async () => {
      const mockGraphWithAliases = {
        nodes: [{ type: '123' }],
        definitions: {
          subgraphs: [{ id: '123' }]
        },
        extra: {
          BlueprintSearchAliases: ['alias1', 'alias2', 'my workflow']
        }
      }
      await mockFetch({ 'test-with-aliases.json': mockGraphWithAliases })

      const nodeDef = useNodeDefStore().nodeDefs.find(
        (d) => d.name === 'SubgraphBlueprint.test-with-aliases'
      )
      expect(nodeDef).toBeDefined()
      expect(nodeDef?.search_aliases).toEqual([
        'alias1',
        'alias2',
        'my workflow'
      ])
    })

    it('should not have search_aliases if not provided', async () => {
      await mockFetch({ 'test.json': mockGraph })

      const nodeDef = useNodeDefStore().nodeDefs.find(
        (d) => d.name === 'SubgraphBlueprint.test'
      )
      expect(nodeDef).toBeDefined()
      expect(nodeDef?.search_aliases).toBeUndefined()
    })

    it('should include description from workflow extra', async () => {
      const mockGraphWithDescription = {
        nodes: [{ type: '123' }],
        definitions: {
          subgraphs: [{ id: '123' }]
        },
        extra: {
          BlueprintDescription: 'This is a test blueprint'
        }
      }
      await mockFetch({
        'test-with-description.json': mockGraphWithDescription
      })

      const nodeDef = useNodeDefStore().nodeDefs.find(
        (d) => d.name === 'SubgraphBlueprint.test-with-description'
      )
      expect(nodeDef).toBeDefined()
      expect(nodeDef?.description).toBe('This is a test blueprint')
    })

    it('should not duplicate metadata in both workflow extra and subgraph extra when publishing', async () => {
      const subgraph = createTestSubgraph()
      const subgraphNode = createTestSubgraphNode(subgraph)
      const graph = subgraphNode.graph!
      graph.add(subgraphNode)

      // Set metadata on the subgraph's extra (as the commands do)
      subgraph.extra = {
        BlueprintDescription: 'Test description',
        BlueprintSearchAliases: ['alias1', 'alias2']
      }

      vi.mocked(comfyApp.canvas).selectedItems = new Set([subgraphNode])
      vi.mocked(comfyApp.canvas)._serializeItems = vi.fn(() => {
        const serializedSubgraph = fromPartial<ExportedSubgraph>({
          ...subgraph.serialize(),
          links: [],
          groups: [],
          version: 1
        })
        return {
          nodes: [subgraphNode.serialize()],
          subgraphs: [serializedSubgraph]
        }
      })

      let savedWorkflowData: Record<string, unknown> | null = null
      vi.mocked(api.storeUserData).mockImplementation(async (_path, data) => {
        savedWorkflowData = JSON.parse(data as string)
        return {
          status: 200,
          json: () =>
            Promise.resolve({
              path: 'subgraphs/testname.json',
              modified: Date.now(),
              size: 2
            })
        } as Response
      })

      await mockFetch({ 'testname.json': mockGraph })
      await store.publishSubgraph()

      expect(savedWorkflowData).not.toBeNull()

      // Metadata should be in top-level extra
      expect(savedWorkflowData!.extra).toEqual({
        BlueprintDescription: 'Test description',
        BlueprintSearchAliases: ['alias1', 'alias2']
      })

      // Metadata should NOT be in subgraph's extra
      const definitions = savedWorkflowData!.definitions as {
        subgraphs: Array<{ extra?: Record<string, unknown> }>
      }
      const subgraphExtra = definitions.subgraphs[0]?.extra
      expect(subgraphExtra?.BlueprintDescription).toBeUndefined()
      expect(subgraphExtra?.BlueprintSearchAliases).toBeUndefined()
    })
  })

  describe('subgraph definition category', () => {
    it('should use User override for user blueprints even with definition category', async () => {
      const mockGraphWithCategory = {
        nodes: [{ type: '123' }],
        definitions: {
          subgraphs: [{ id: '123', category: 'Image Processing' }]
        }
      }
      await mockFetch({ 'user-bp.json': mockGraphWithCategory })

      const nodeDef = useNodeDefStore().nodeDefs.find(
        (d) => d.name === 'SubgraphBlueprint.user-bp'
      )
      expect(nodeDef).toBeDefined()
      expect(nodeDef?.category).toBe('Subgraph Blueprints/User')
    })

  })

})

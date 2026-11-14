import { describe, expect, it } from 'vitest'

import type { AugmentedResultItem } from '@/utils/resultItem'
import { resultItemPreviewUrl } from '@/utils/resultItemUrl'

function resultItem(
  overrides: Partial<AugmentedResultItem>
): AugmentedResultItem {
  return {
    filename: 'out.png',
    subfolder: '',
    type: 'output',
    nodeId: '3',
    mediaType: 'images',
    ...overrides
  }
}

describe('resultItemPreviewUrl', () => {
  it.for([
    {
      filename: 'render.exr',
      preview_id: 'p1',
      pathname: '/api/assets/p1/content',
      preview: null
    },
    {
      filename: 'render.HDR',
      preview_id: 'p1',
      pathname: '/api/assets/p1/content',
      preview: null
    },
    {
      filename: 'render.exr',
      preview_id: undefined,
      pathname: '/api/view',
      preview: 'webp'
    },
    {
      filename: 'render.png',
      preview_id: 'p1',
      pathname: '/api/view',
      preview: null
    }
  ])(
    'resolves $filename with preview_id $preview_id to $pathname',
    ({ filename, preview_id, pathname, preview }) => {
      const url = new URL(
        resultItemPreviewUrl(resultItem({ filename, preview_id })),
        window.location.origin
      )
      expect(url.pathname).toBe(pathname)
      expect(url.searchParams.get('preview')).toBe(preview)
    }
  )
})

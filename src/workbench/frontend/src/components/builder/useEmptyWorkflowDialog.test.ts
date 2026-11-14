import { assert, describe, expect, it, vi } from 'vitest'

import { useDialogService } from '@/services/dialogService'

import { useEmptyWorkflowDialog } from './useEmptyWorkflowDialog'

vi.mock(import('@/services/dialogService'))

function showDialog() {
  const options = { onEnterBuilder: vi.fn(), onDismiss: vi.fn() }
  useEmptyWorkflowDialog().show(options)
  const [{ props }] = vi.mocked(useDialogService().showLayoutDialog).mock
    .calls[0]
  assert('onBackToWorkflow' in props)
  const { onBackToWorkflow } = props
  assert(typeof onBackToWorkflow === 'function')
  return { options, onBackToWorkflow }
}

describe('useEmptyWorkflowDialog', () => {
  it('dismisses when the user goes back to the workflow', () => {
    const { options, onBackToWorkflow } = showDialog()

    onBackToWorkflow()

    expect(options.onDismiss).toHaveBeenCalledOnce()
    expect(options.onEnterBuilder).not.toHaveBeenCalled()
  })
})

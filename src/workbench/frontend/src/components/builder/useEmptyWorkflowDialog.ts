import { useDialogService } from '@/services/dialogService'
import { useDialogStore } from '@/stores/dialogStore'

import EmptyWorkflowDialogContent from './EmptyWorkflowDialogContent.vue'

const DIALOG_KEY = 'builder-empty-workflow'

export function useEmptyWorkflowDialog() {
  const dialogService = useDialogService()
  const dialogStore = useDialogStore()

  function show(options: {
    onEnterBuilder: () => void
    onDismiss: () => void
  }) {
    dialogService.showLayoutDialog({
      key: DIALOG_KEY,
      component: EmptyWorkflowDialogContent,
      props: {
        onBackToWorkflow: () => {
          closeDialog()
          options.onDismiss()
        },
      }
    })
  }

  function closeDialog() {
    dialogStore.closeDialog({ key: DIALOG_KEY })
  }

  return { show }
}

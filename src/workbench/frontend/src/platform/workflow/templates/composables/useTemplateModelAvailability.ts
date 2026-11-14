import type { ModelFile } from '@/platform/workflow/validation/schemas/workflowSchema'
import { resolveTemplateModelAvailability } from '@/platform/workflow/templates/utils/templateModelAvailability'

export function useTemplateModelAvailability() {
  async function resolveAvailability(models: readonly ModelFile[]) {
    // Model inventory is not part of the astronomy engine.
    return resolveTemplateModelAvailability(models, { isComplete: true, models: [] })
  }
  return { resolveAvailability }
}

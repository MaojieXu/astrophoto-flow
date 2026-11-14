import { defineConfig } from 'vitest/config'

// Gate specs are the only tests this repository runs: unit-level checks of the
// pure helpers in `scripts/`. `reference/` holds an external checkout and is out
// of scope.
export default defineConfig({
  test: {
    include: ['scripts/**/*.spec.ts'],
    exclude: ['reference/**', 'node_modules/**'],
  },
})

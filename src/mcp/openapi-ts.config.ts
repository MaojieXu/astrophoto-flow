import { defineConfig } from '@hey-api/openapi-ts';

// NodeNext needs explicit relative import extensions, so generated imports use
// `.js`. Input is the committed snapshot exported by the FastAPI app.
export default defineConfig({
  input: '../../docs/api/openapi.json',
  output: {
    path: 'src/generated/api',
    module: { extension: '.js' },
  },
  plugins: ['@hey-api/typescript', '@hey-api/client-fetch', 'zod', '@hey-api/sdk'],
});

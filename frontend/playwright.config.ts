import { defineConfig } from "@playwright/test";

// Starts backend (mock AI, throwaway DB) and frontend, then runs Daniel's journey.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: { baseURL: "http://127.0.0.1:5173", trace: "retain-on-failure" },
  webServer: [
    {
      command: "cd ../backend && rm -f /tmp/insurendclaim-e2e.db && LLM_PROVIDER=mock INSURE_DB_PATH=/tmp/insurendclaim-e2e.db INSURE_UPLOAD_DIR=/tmp/insurendclaim-e2e-uploads python3 -m uvicorn app.main:app --port 8000",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npx vite --port 5173 --strictPort --host 127.0.0.1",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});

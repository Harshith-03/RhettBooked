import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// No hard-coded backend URL here; the app reads import.meta.env.VITE_API_URL.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});

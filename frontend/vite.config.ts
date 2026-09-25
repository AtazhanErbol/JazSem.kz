import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          forms: ["zod", "react-hook-form", "@hookform/resolvers"],
          i18n: ["i18next", "react-i18next"],
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": process.env.API_PROXY || "http://localhost:8000",
      "/health": process.env.API_PROXY || "http://localhost:8000",
    },
  },
});

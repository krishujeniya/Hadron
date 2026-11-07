import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // GitHub Pages deploys under https://<user>.github.io/<repo>/
  base: process.env.VITE_BASE_PATH || process.env.BASE_PATH || "/Hadron/",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "next/link": path.resolve(__dirname, "./src/compat/next/link.tsx"),
      "next/navigation": path.resolve(__dirname, "./src/compat/next/navigation.tsx"),
      "next/dynamic": path.resolve(__dirname, "./src/compat/next/dynamic.tsx"),
    },
  },
  define: {
    "process.env.NEXT_PUBLIC_APP_URL": JSON.stringify(
      process.env.VITE_APP_URL || process.env.NEXT_PUBLIC_APP_URL || "https://krishujeniya.github.io/Hadron"
    ),
    "process.env.NEXT_PUBLIC_API_BASE_URL": JSON.stringify(
      process.env.VITE_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "https://hadron-backend.vercel.app"
    ),
    "process.env.NEXT_PUBLIC_API_DIRECT": JSON.stringify(
      process.env.VITE_API_DIRECT || process.env.NEXT_PUBLIC_API_DIRECT || "1"
    ),
    "process.env.NEXT_PUBLIC_BASE_PATH": JSON.stringify(
      process.env.VITE_BASE_PATH || process.env.NEXT_PUBLIC_BASE_PATH || "/Hadron"
    ),
    "process.env.NODE_ENV": JSON.stringify(process.env.NODE_ENV || "production"),
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom"],
        },
      },
    },
  },
  server: {
    port: 5173,
    host: true,
  },
});

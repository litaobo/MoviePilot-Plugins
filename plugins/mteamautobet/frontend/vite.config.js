import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import federation from "@originjs/vite-plugin-federation";

export default defineConfig({
  plugins: [
    vue(),
    federation({
      name: "mteam-auto-bet",
      filename: "remoteEntry.js",
      exposes: {
        "./Settings": "./frontend/src/components/Settings.vue",
        "./Dashboard": "./frontend/src/components/Dashboard.vue"
      },
      shared: ["vue", "vuetify"]
    })
  ],
  build: {
    target: "esnext"
  }
});
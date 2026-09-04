import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Превью-инструмент подставляет порт через $env:PORT (см. .claude/launch.json);
    // 5173 — запасной вариант для ручного запуска (см. README).
    port: Number(process.env.PORT) || 5173,
    strictPort: false,
    // host: true — слушать на всех интерфейсах (0.0.0.0), не только на
    // "localhost". Без этого Vite по умолчанию биндится так, что
    // превью-инструмент (отдельный сетевой namespace) не может достучаться.
    host: true,
  },
});

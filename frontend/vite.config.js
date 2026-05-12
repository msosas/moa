import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Parse VITE_ALLOWED_HOSTS from the env file:
//   - empty / unset -> Vite defaults (localhost + 127.0.0.1)
//   - "all" or "*"  -> disable the host check entirely
//   - comma-separated list -> allow exactly those hostnames
function parseAllowedHosts(raw) {
  if (!raw) return undefined;
  const trimmed = raw.trim();
  if (!trimmed) return undefined;
  if (trimmed === '*' || trimmed.toLowerCase() === 'all' || trimmed.toLowerCase() === 'true') return true;
  return trimmed.split(',').map((h) => h.trim()).filter(Boolean);
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: { usePolling: true },
    allowedHosts: parseAllowedHosts(process.env.VITE_ALLOWED_HOSTS),
  },
});

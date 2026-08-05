// PM2 process manager config — auto-restarts both services.
//   pm2 start ecosystem.config.js && pm2 save
// Logs: pm2 logs   |   Status: pm2 status   |   Restart: pm2 restart all
const path = require("path");
const ROOT = __dirname;

module.exports = {
  apps: [
    {
      name: "oca-backend",
      cwd: path.join(ROOT, "backend"),
      // venv uvicorn has a shebang to the venv python; run it directly.
      script: ".venv/bin/uvicorn",
      args: "app.main:app --host 127.0.0.1 --port 8000",
      interpreter: "none",
      autorestart: true,
      max_restarts: 15,
      min_uptime: "10s",
      restart_delay: 2000,
      env: { PYTHONUNBUFFERED: "1" },
    },
    {
      name: "oca-frontend",
      cwd: path.join(ROOT, "frontend"),
      // production server (stable) — build first with `npm run build`.
      script: "node_modules/.bin/next",
      args: "start -p 3000 -H 127.0.0.1",
      interpreter: "none",
      autorestart: true,
      max_restarts: 15,
      min_uptime: "10s",
      restart_delay: 2000,
      env: { NODE_ENV: "production", PORT: "3000" },
    },
  ],
};

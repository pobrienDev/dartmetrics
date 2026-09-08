// Cross-platform backend launcher for .claude/launch.json.
//
// The venv interpreter lives at backend/.venv/bin/python on macOS and
// Linux but backend/.venv/Scripts/python.exe on Windows; node is on
// both machines' PATH (the frontend needs it), so it does the picking.

const { spawn } = require('node:child_process')
const { existsSync } = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const venv = path.join(root, 'backend', '.venv')
const python =
  process.platform === 'win32'
    ? path.join(venv, 'Scripts', 'python.exe')
    : path.join(venv, 'bin', 'python')

if (!existsSync(python)) {
  console.error(`No virtualenv at ${venv} — see README "Local development".`)
  process.exit(1)
}

const child = spawn(
  python,
  ['-m', 'uvicorn', 'app.main:app', '--port', '8000', '--app-dir', 'backend', '--reload'],
  { cwd: root, stdio: 'inherit' },
)
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => child.kill(signal))
}
child.on('exit', (code) => process.exit(code ?? 0))

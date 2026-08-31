// Shared helpers for SkillBridge scripts.
import { existsSync, mkdirSync, rmSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

export function log(msg) {
  process.stdout.write(`==> ${msg}\n`)
}

export function resolvePython() {
  const candidates = []
  if (process.env.PYTHON_BIN) candidates.push(process.env.PYTHON_BIN)
  candidates.push('python', 'python3')
  if (process.platform === 'win32') candidates.push('py')

  for (const c of candidates) {
    const r = spawnSync(c, ['--version'], { stdio: 'ignore' })
    if (!r.error && r.status === 0) return c
  }
  const known = []
  if (process.platform === 'win32') {
    const base = path.join(process.env.USERPROFILE || '', 'AppData', 'Local', 'Programs', 'Python')
    for (const version of ['Python313', 'Python312', 'Python311', 'Python310']) {
      known.push(path.join(base, version, 'python.exe'))
    }
    known.push('C:/Python312/python.exe')
  } else {
    known.push('/usr/bin/python3')
  }
  for (const candidate of known) {
    if (candidate && existsSync(candidate)) return candidate
  }
  return null
}

export function venvPython(venvDir) {
  const candidates =
    process.platform === 'win32'
      ? [path.join(venvDir, 'Scripts', 'python.exe')]
      : [path.join(venvDir, 'bin', 'python3'), path.join(venvDir, 'bin', 'python')]
  for (const c of candidates) {
    if (existsSync(c)) return c
  }
  return null
}

export function ensureVenv() {
  const venvDir = path.join(ROOT, process.env.VENV_DIR || '.venv')
  let venvPy = process.env.VENV_PY || venvPython(venvDir)
  if (!venvPy) {
    if (existsSync(venvDir)) {
      log('Recreating incomplete virtual environment')
      rmSync(venvDir, { recursive: true, force: true })
    }
    log('Creating Python virtual environment')
    mkdirSync(venvDir, { recursive: true })
    const py = resolvePython()
    if (!py) {
      throw new Error('Python 3 not found. Install Python 3.10+ and try again.')
    }
    run(py, ['-m', 'venv', venvDir])
    venvPy = venvPython(venvDir)
  }
  if (!venvPy) {
    throw new Error('Virtual environment was created but no Python was found under .venv/')
  }
  return venvPy
}

export function npmCmd() {
  return process.platform === 'win32' ? 'npm.cmd' : 'npm'
}

export function run(cmd, argList, opts = {}) {
  const r = spawnSync(cmd, argList, {
    cwd: opts.cwd || ROOT,
    stdio: opts.stdio === undefined ? 'inherit' : opts.stdio,
    shell: process.platform === 'win32',
    env: { ...process.env, ...(opts.env || {}) },
  })
  if (r.status !== 0) {
    if (!opts.allowFail) {
      process.stderr.write(`\nCommand failed: ${cmd} ${argList.join(' ')}\n`)
      process.exit(r.status === null ? 1 : r.status)
    }
    return false
  }
  return true
}

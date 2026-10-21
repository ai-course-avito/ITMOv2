import { realpathSync } from 'node:fs'
import { execFile } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { relative, resolve, sep, join } from 'node:path'

const project = fileURLToPath(new URL('../../', import.meta.url))
const editTools = new Set(['edit', 'write', 'apply_patch', 'multiedit'])

function pathsFrom(args = {}, metadata = {}) {
  const paths = [args.filePath, args.path]
  for (const edit of args.edits ?? []) paths.push(edit.filePath, edit.path)
  for (const file of metadata.files ?? []) paths.push(file.filePath, file.path, file.relativePath)
  for (const match of (args.patchText ?? args.patch ?? '').matchAll(/^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$/gm)) {
    paths.push(match[1].trim())
  }
  return paths.filter(path => typeof path === 'string')
}

function affectsCode(path, directory) {
  const local = relative(project, resolve(directory, path)).split(sep).join('/')
  if (local.startsWith('../') || local.split('/').some(part =>
    ['node_modules', '.venv', 'dist', 'verification', '__pycache__', '.git'].includes(part))) return false
  return /^(backend\/(app|tests)\/.*\.py|backend\/(requirements[^/]*\.txt|pytest\.ini)|frontend\/(src\/.*\.(tsx?|jsx?|css)|package(-lock)?\.json|.*config\.(ts|json)|index\.html)|scripts\/.*\.(py|sh|mjs|js)|\.agents\/skills\/verify-flight-features\/scripts\/.*\.py|\.opencode\/plugins\/.*\.[jt]s)$/.test(local)
}

function verify() {
  const environment = { ...process.env }
  delete environment.IGNAV_API_KEY
  return new Promise(resolveResult => {
    execFile(join(project, 'backend/.venv/bin/python'), [
      join(project, '.agents/skills/verify-flight-features/scripts/run.py'),
      '--report', 'verification/after-edit.md',
    ], { cwd: project, env: environment, timeout: 300_000, maxBuffer: 1024 * 1024 }, (error, stdout, stderr) => {
      const status = error ? 'FAIL' : 'PASS'
      const details = [stdout, stderr, error ? `Runner error: ${error.message}` : ''].filter(Boolean).join('\n')
      resolveResult({ status, details: details.slice(-24000), report: 'verification/after-edit.md' })
    })
  })
}

export const VerifyAfterEdit = async ({ directory }) => {
  directory = realpathSync(directory)
  const pending = new Map()
  let queue = Promise.resolve()
  return {
    'tool.execute.before': async (input, output) => {
      if (!editTools.has(input.tool)) return
      // Older OpenCode versions do not include args in the after event.
      if (pending.size >= 256) pending.delete(pending.keys().next().value)
      pending.set(`${input.sessionID}:${input.callID}`, pathsFrom(output.args))
    },
    'tool.execute.after': async (input, output) => {
      if (!editTools.has(input.tool)) return
      const key = `${input.sessionID}:${input.callID}`
      const paths = [...(pending.get(key) ?? []), ...pathsFrom(input.args, output.metadata)]
      pending.delete(key)
      if (!paths.some(path => affectsCode(path, directory))) return
      const task = queue.then(verify)
      queue = task.catch(() => {})
      const result = await task
      output.output = `${output.output ?? ''}\n\n[verify-flight-features: ${result.status}]\n${result.details}`
      output.metadata = { ...output.metadata, flightVerification: result }
    },
  }
}

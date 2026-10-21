// Standalone harness for OpenCode's hook contract; no model/API calls.
import { writeFile, unlink, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import { VerifyAfterEdit } from '../.opencode/plugins/verify-after-edit.js'

const project = fileURLToPath(new URL('../', import.meta.url))
const filePath = join(project, `backend/app/.hook-demo-${process.pid}.py`)
const hooks = await VerifyAfterEdit({ directory: project })
const input = { tool: 'write', sessionID: 'local-demo', callID: 'write-1', args: { filePath } }
let created = false
try {
  await hooks['tool.execute.before'](input, { args: input.args })
  await writeFile(filePath, '# Temporary hook demonstration; removed after verification.\n', { flag: 'wx' })
  created = true
  const output = { title: 'Write temporary Python file', output: 'File written successfully.', metadata: {} }
  await hooks['tool.execute.after'](input, output)
  await mkdir(join(project, 'verification'), { recursive: true })
  await writeFile(join(project, 'verification/after-edit-hook.json'), JSON.stringify({
    mode: 'Standalone harness: real file write and runner; OpenCode event invoked by harness',
    generated_at: new Date().toISOString(), tool: input.tool, output,
  }, null, 2) + '\n')
  console.log(output.output)
  if (output.metadata.flightVerification?.status !== 'PASS') process.exitCode = 1
} finally {
  if (created) await unlink(filePath)
}

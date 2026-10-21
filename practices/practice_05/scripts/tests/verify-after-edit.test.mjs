import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, copyFile, writeFile, rm, readFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const source = new URL('../../.opencode/plugins/verify-after-edit.js', import.meta.url)

test('after-edit returns failure to agent, supports before args and patches, skips reports', async () => {
  const root = await mkdtemp(join(tmpdir(), 'flight-hook-'))
  try {
    await mkdir(join(root, '.opencode/plugins'), { recursive: true })
    await mkdir(join(root, 'backend/.venv/bin'), { recursive: true })
    await writeFile(join(root, 'package.json'), '{"type":"module"}')
    await copyFile(source, join(root, '.opencode/plugins/verify-after-edit.js'))
    await writeFile(join(root, 'backend/.venv/bin/python'), '#!/bin/sh\necho called >> calls\necho "intentional runner failure"\nexit 1\n', { mode: 0o755 })
    const { VerifyAfterEdit } = await import(pathToFileURL(join(root, '.opencode/plugins/verify-after-edit.js')))
    const hooks = await VerifyAfterEdit({ directory: root })
    const output = { output: 'File edited', metadata: {} }
    const input = { tool: 'edit', sessionID: 'test', callID: '1' }
    await hooks['tool.execute.before'](input, { args: { filePath: 'backend/app/main.py' } })
    await hooks['tool.execute.after'](input, output)
    assert.match(output.output, /File edited[\s\S]*verify-flight-features: FAIL[\s\S]*intentional runner failure/)
    assert.equal(output.metadata.flightVerification.status, 'FAIL')
    for (const filePath of ['verification/report.py', 'frontend/dist/test.ts', 'backend/.env', '../outside.py']) {
      const ignored = { output: 'unchanged', metadata: {} }
      await hooks['tool.execute.after']({ tool: 'write', args: { filePath } }, ignored)
      assert.equal(ignored.output, 'unchanged')
    }
    const patchOutput = { output: '', metadata: {} }
    await hooks['tool.execute.after']({ tool: 'apply_patch', args: { patchText: '*** Begin Patch\n*** Update File: frontend/src/App.tsx\n*** End Patch' } }, patchOutput)
    assert.equal(patchOutput.metadata.flightVerification.status, 'FAIL')
    assert.equal((await readFile(join(root, 'calls'), 'utf8')).trim().split('\n').length, 2)
  } finally { await rm(root, { recursive: true, force: true }) }
})

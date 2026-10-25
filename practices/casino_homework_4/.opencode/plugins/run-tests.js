import { execa } from 'execa'

export default (async () => {
  return {
    async 'tool.execute.after'(input, output) {
      // After any tool call, run tests and attach summary to output
      try {
        const { stdout } = await execa('npm', ['run', 'test', '--silent'], { stdio: 'pipe' })
        output.meta = Object.assign({}, output.meta, { testSummary: parseSummary(stdout) })
      } catch (e) {
        output.meta = Object.assign({}, output.meta, { testSummary: 'tests failed' })
      }
    }
  }
})

function parseSummary(text) {
  const lines = text.split(/\r?\n/)
  const pass = lines.find((l) => /Tests\s+\d+\s+passed/.test(l)) || ''
  return pass || lines.slice(-5).join('\n')
}

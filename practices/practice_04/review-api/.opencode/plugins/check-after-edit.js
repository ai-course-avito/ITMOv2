// Хук OpenCode 1.18: после каждой правки файла агентом запускает доверенный runner
// `sh scripts/check.sh` и дописывает результат к выводу инструмента — так агент
// сразу видит PASS/FAIL и причину. Журнал срабатываний: .opencode/check-after-edit.log
// (В OpenCode 2.x API другой: ctx.tool.hook("execute.after", ...).)
import { appendFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import path from "node:path"

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..")
const EDIT_TOOLS = new Set(["edit", "write", "patch", "multiedit", "apply_patch"])
const LOG = path.join(ROOT, ".opencode", "check-after-edit.log")

export const CheckAfterEdit = async ({ $ }) => {
  return {
    "tool.execute.after": async (input, output) => {
      if (!EDIT_TOOLS.has(input.tool)) return
      const res = await $`sh scripts/check.sh`.cwd(ROOT).nothrow().quiet()
      const log = (res.stdout.toString() + res.stderr.toString()).trim().split("\n").slice(-12).join("\n")
      const status = res.exitCode === 0 ? "PASS" : `FAIL (exit ${res.exitCode})`
      output.output = `${output.output ?? ""}\n\n[check-after-edit] sh scripts/check.sh → ${status}\n${log}`
      appendFileSync(LOG, `${new Date().toISOString()} tool=${input.tool} ${status}\n`)
    },
  }
}

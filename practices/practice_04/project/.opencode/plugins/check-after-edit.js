// OpenCode 2 plugin: check-after-edit
// Appends scripts/check.sh result to tool outputs after edit/write/patch tools

/**
 * @typedef {import('@opencode-ai/plugin').Plugin} Plugin
 */

/**
 * Named export as requested. The plugin also serves as default module's `server` export below
 * to ensure compatibility with the loader that expects a PluginModule.
 * @type {Plugin}
 */
export const CheckAfterEdit = async ({ directory, $ }) => {
  const EDIT_TOOLS = new Set(["edit", "write", "patch"]);

  return {
    /**
     * @param {{ tool: string; sessionID: string; callID: string; args: any }} input
     * @param {{ title: string; output: string; metadata: any }} output
     */
    "tool.execute.after": async (input, output) => {
      try {
        if (!EDIT_TOOLS.has(input.tool)) return;

        const res = await $`sh scripts/check.sh`.cwd(directory).quiet().nothrow();

        const limit = 2000;
        const stdout = (res.stdout ? res.stdout.toString("utf8") : "");
        const stderr = (res.stderr ? res.stderr.toString("utf8") : "");

        const trunc = (s) => (s.length > limit ? s.slice(0, limit) + `\n…[trimmed ${s.length - limit} chars]` : s);

        const pass = res.exitCode === 0;
        const header = `\n\n[check-after-edit] ${pass ? "PASS" : "FAIL"} (exit ${res.exitCode})`;
        const body = [
          stdout ? `\nstdout:\n${trunc(stdout)}` : "",
          stderr ? `\nstderr:\n${trunc(stderr)}` : "",
        ]
          .filter(Boolean)
          .join("");

        output.output += header + body;
      } catch (err) {
        const msg = err && typeof err === "object" && "message" in err ? err.message : String(err);
        output.output += `\n\n[check-after-edit] ERROR running scripts/check.sh: ${msg}`;
      }
    },
  };
};

// Also export a default PluginModule for compatibility with loaders expecting `{ server }`.
export default {
  id: "check-after-edit",
  setup: CheckAfterEdit,
};

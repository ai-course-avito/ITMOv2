import { spawnSync } from "node:child_process";

console.log("=== Automatic project check ===");
console.log("Запуск тестов...");

const npmCommand =
  process.platform === "win32"
    ? "npm.cmd"
    : "npm";

const result = spawnSync(
  npmCommand,
  ["test"],
  {
    stdio: "inherit"
  }
);

if (result.error) {
  console.error("Не удалось запустить проверку:");
  console.error(result.error.message);
  process.exit(1);
}

if (result.status !== 0) {
  console.error("Project checks failed.");
  process.exit(result.status ?? 1);
}

console.log("Project checks passed.");
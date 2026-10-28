const fs = require("fs");
const file = require.resolve("mcp-pg-server/dist/index.js");
const lines = fs.readFileSync(file, "utf8").split("\n");
if (lines[0].startsWith("#!") && lines[1] && lines[1].startsWith("#!")) {
  lines.splice(1, 1);
  fs.writeFileSync(file, lines.join("\n"));
  console.log("fix-shebang: removed duplicated shebang");
} else {
  console.log("fix-shebang: nothing to fix");
}

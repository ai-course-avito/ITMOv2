import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

const transport = new StdioClientTransport({
  command: "node",
  args: ["server.js"]
});

const client = new Client({
  name: "calculator-validator-test-client",
  version: "1.0.0"
});

await client.connect(transport);

console.log("=== MCP tools ===");

const tools = await client.listTools();

for (const tool of tools.tools) {
  console.log(`- ${tool.name}`);
}

console.log("\n=== Успешный вызов ===");

const success = await client.callTool({
  name: "validate_calculation_input",
  arguments: {
    a: 10,
    b: 2,
    operation: "divide"
  }
});

console.log(
  success.content
    .map((item) => item.text ?? "")
    .join("\n")
);

console.log("\n=== Ошибочный вызов ===");

const failure = await client.callTool({
  name: "validate_calculation_input",
  arguments: {
    a: 10,
    b: 0,
    operation: "divide"
  }
});

console.log(
  failure.content
    .map((item) => item.text ?? "")
    .join("\n")
);

await client.close();
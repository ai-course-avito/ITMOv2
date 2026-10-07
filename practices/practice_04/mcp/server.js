import { McpServer } from "@modelcontextprotocol/server";
import { serveStdio } from "@modelcontextprotocol/server/stdio";
import * as z from "zod/v4";

const operations = [
  "add",
  "subtract",
  "multiply",
  "divide"
];

function createServer() {
  const server = new McpServer({
    name: "calculator-validator",
    version: "1.0.0"
  });

  server.registerTool(
    "validate_calculation_input",
    {
      description:
        "Проверяет входные данные для арифметической операции.",

      inputSchema: z.object({
        a: z.number().describe("Первое число"),

        b: z.number().describe("Второе число"),

        operation: z.enum(operations)
          .describe("Арифметическая операция")
      })
    },

    async ({ a, b, operation }) => {
      if (!Number.isFinite(a) || !Number.isFinite(b)) {
        return {
          isError: true,
          content: [
            {
              type: "text",
              text:
                "Ошибка: a и b должны быть конечными числами."
            }
          ]
        };
      }

      if (operation === "divide" && b === 0) {
        return {
          isError: true,
          content: [
            {
              type: "text",
              text:
                "Ошибка: деление на ноль запрещено."
            }
          ]
        };
      }

      return {
        content: [
          {
            type: "text",
            text:
              `Проверка успешна: операция "${operation}" ` +
              `допустима для a=${a}, b=${b}.`
          }
        ]
      };
    }
  );

  return server;
}

serveStdio(createServer);
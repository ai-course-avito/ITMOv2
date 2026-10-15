"""Живая проверка MCP diff-inspector: запускает server.py как подпроцесс (stdio),
делает list_tools и несколько вызовов inspect_diff. Печатает результаты как есть.

Запуск из корня ai-review-api:  python mcp_server/smoke_client.py
(нужен python с установленным пакетом mcp)
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = Path(__file__).resolve().parent / "server.py"

GOOD_DIFF = """\
diff --git a/app/main.py b/app/main.py
index 111..222 100644
--- a/app/main.py
+++ b/app/main.py
@@ -1,3 +1,4 @@
 import os
-old = 1
+new = 1
+new2 = 2
 print(old)
diff --git a/docs/new.md b/docs/new.md
new file mode 100644
index 0000000..abc
--- /dev/null
+++ b/docs/new.md
@@ -0,0 +1,2 @@
+hello
+world
diff --git a/old.txt b/old.txt
deleted file mode 100644
index abc..0000000
--- a/old.txt
+++ /dev/null
@@ -1,2 +0,0 @@
-a
-b
diff --git a/src/a.py b/src/b.py
similarity index 90%
rename from src/a.py
rename to src/b.py
--- a/src/a.py
+++ b/src/b.py
@@ -1 +1 @@
-print(1)
+print(2)
diff --git a/img/logo.png b/img/logo.png
new file mode 100644
index 0000000..abc
Binary files /dev/null and b/img/logo.png differ
"""

CASES = [
    ("1. OK: нормальный diff (5 файлов: изменен, новый, удален, переименован, бинарный)",
     {"diff": GOOD_DIFF}),
    ("2. OK: тот же diff, но max_bytes=100 -> too_large=true, would_be_accepted=false",
     {"diff": GOOD_DIFF, "max_bytes": 100}),
    ("3. ERROR: пустая строка", {"diff": ""}),
    ("4. ERROR: только пробелы и переводы строк", {"diff": "   \n\t\n"}),
    ("5. ERROR: мусорный текст без признаков diff", {"diff": "привет, это просто текст, а не diff"}),
    ("6. ERROR: max_bytes = 0", {"diff": GOOD_DIFF, "max_bytes": 0}),
    ("7. ERROR: max_bytes < 0", {"diff": GOOD_DIFF, "max_bytes": -5}),
    ("8. ERROR: diff не строка (число 123)", {"diff": 123}),
]


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    bad_flags = 0
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"server: {init.serverInfo.name} {init.serverInfo.version}, protocol {init.protocolVersion}")

            tools = await session.list_tools()
            print(f"\n=== list_tools: {len(tools.tools)} tool(s) ===")
            for t in tools.tools:
                print(f"name: {t.name}")
                print(f"description: {t.description}")
                print(f"inputSchema: {t.inputSchema}")

            for title, args in CASES:
                print(f"\n=== {title} ===")
                arg_preview = {k: (v if k != "diff" or len(str(v)) < 60 else f"<{len(v)} chars>") for k, v in args.items()}
                print(f"arguments: {arg_preview}")
                result = await session.call_tool("inspect_diff", args)
                print(f"isError: {result.isError}")
                for block in result.content:
                    print(f"content[{block.type}]: {getattr(block, 'text', block)}")
                if result.structuredContent is not None:
                    print(f"structuredContent: {result.structuredContent}")
                expect_error = title.split(" ")[1].startswith("ERROR")
                if bool(result.isError) != expect_error:
                    bad_flags += 1
                    print("!!! неожиданный isError")

    print(f"\nИТОГ: {'OK, все ожидания по isError совпали' if bad_flags == 0 else f'РАСХОЖДЕНИЙ: {bad_flags}'}")
    return 1 if bad_flags else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

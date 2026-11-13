from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calculator", host="0.0.0.0", port=9100, stateless_http=True)


@mcp.tool()
def calculate(expression: str) -> str:
    """Evaluate a basic Python arithmetic expression and return the exact result.

    Supports +, -, *, /, //, %, **, parentheses, and integer/float literals.
    """
    allowed_chars = set("0123456789+-*/().% ")
    if not all(char in allowed_chars for char in expression):
        raise ValueError("Expression contains disallowed characters")

    return str(eval(expression, {"__builtins__": {}}, {}))


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

"""omnixon-mcp: the Omnixon API as an MCP server whose tools follow the role of the caller's token."""

import os


def main() -> None:
    import uvicorn

    from .server import App

    # no access log: a token may be in the URL (?token=)
    uvicorn.run(
        App(),
        host=os.environ.get("OMNIXON_MCP_HOST", "0.0.0.0"),
        port=int(os.environ.get("OMNIXON_MCP_PORT", "8090")),
        access_log=False,
    )

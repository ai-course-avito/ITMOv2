import json
import subprocess
import sys
from pathlib import Path

SERVER_CMD = [sys.executable, 'mcp/pptx-reader/server.py']
DECK_PATH = Path('practices/practice_03/output_first2.pptx').resolve()


def send(proc, msg):
    proc.stdin.write((json.dumps(msg) + "\n").encode())
    proc.stdin.flush()


def recv(proc):
    line = proc.stdout.readline()
    if not line:
        return None
    return json.loads(line.decode())


def main():
    if not DECK_PATH.exists():
        print(f'ERROR: deck not found: {DECK_PATH}')
        sys.exit(2)

    proc = subprocess.Popen(
        SERVER_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # initialize
    send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    print('initialize ->', recv(proc))

    # list tools
    send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    print('tools/list ->', recv(proc))

    # call count_slides
    send(proc, {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "count_slides", "arguments": {"path": str(DECK_PATH)}}
    })
    print('tools/call count_slides ->', recv(proc))

    # call get_slide_title for indices 0 and 1
    for i in (0, 1):
        send(proc, {
            "jsonrpc": "2.0",
            "id": 10 + i,
            "method": "tools/call",
            "params": {"name": "get_slide_title", "arguments": {"path": str(DECK_PATH), "index": i}}
        })
        print(f'tools/call get_slide_title({i}) ->', recv(proc))

    proc.kill()


if __name__ == '__main__':
    main()

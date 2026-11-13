import json
import subprocess
import sys
from pathlib import Path

SERVER_CMD = [sys.executable, 'mcp/pptx-reader/server.py']


def send(proc, msg):
    proc.stdin.write((json.dumps(msg) + "\n").encode())
    proc.stdin.flush()


def recv(proc):
    line = proc.stdout.readline()
    if not line:
        return None
    return json.loads(line.decode())


def main():
    proc = subprocess.Popen(
        SERVER_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # initialize
    send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    print('initialize ->', recv(proc))

    # count_slides on nonexistent path
    send(proc, {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "count_slides", "arguments": {"path": "mcp/nonexistent.pptx"}}
    })
    print('tools/call count_slides (nonexistent) ->', recv(proc))

    # get_slide_title with index=999 on an existing deck (expect INDEX_OUT_OF_RANGE)
    deck = str(Path('practices/practice_03/output_first2.pptx').resolve())
    send(proc, {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "get_slide_title", "arguments": {"path": deck, "index": 999}}
    })
    print('tools/call get_slide_title(index=999) ->', recv(proc))

    proc.kill()


if __name__ == '__main__':
    main()

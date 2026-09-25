"""Loopback-only transparent Ollama relay; retain request metadata, never reasoning."""
import hashlib
import http.client
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Relay:
    def __init__(self):
        self.records = []
        self.stem = None
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.0'

            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                data = json.loads(body)
                messages = data.get('messages', [])
                record = {
                    'stem': outer.stem, 'path': self.path,
                    'parameters': {k: v for k, v in data.items() if k not in ('messages', 'tools')},
                    'message_roles': [m.get('role') for m in messages],
                    'system_sha256': [hashlib.sha256(str(m.get('content')).encode()).hexdigest()
                                      for m in messages if m.get('role') == 'system'],
                    'tool_names': [t.get('function', {}).get('name') for t in data.get('tools', [])],
                    'gold_marker_present': any('Эталоны — только для рабочего агента' in str(m.get('content')) for m in messages),
                }
                outer.records.append(record)
                conn = http.client.HTTPConnection('127.0.0.1', 11434, timeout=600)
                try:
                    conn.request('POST', self.path, body, {'Content-Type': 'application/json'})
                    response = conn.getresponse()
                    record['status'] = response.status
                    self.send_response(response.status)
                    self.send_header('Content-Type', response.getheader('Content-Type', 'application/json'))
                    self.end_headers()
                    while chunk := response.read1(65536):
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    record['client_disconnected'] = True
                finally:
                    conn.close()

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server.server_port}/v1'

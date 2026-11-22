import http from 'node:http';

const routes = new Map([
  ['/webhook/e6bde7c5-c7dc-43a3-a805-0aa2d2c8cfac/webhook', new Set(['pull_request', 'issue_comment', 'ping'])],
  ['/webhook/cc134c9b-a3e3-4dfa-baef-8c40cd9dbe5b/webhook', new Set(['issues', 'ping'])],
]);
const maxBytes = 1024 * 1024;

const gateway = http.createServer(async (req, res) => {
  const events = routes.get(req.url);
  if (req.method !== 'POST' || !events) {
    res.writeHead(404).end();
    return;
  }
  const event = req.headers['x-github-event'];
  const signature = req.headers['x-hub-signature-256'];
  if (!events.has(event) || typeof signature !== 'string' || !/^sha256=[0-9a-f]{64}$/.test(signature)) {
    res.writeHead(401).end();
    return;
  }
  try {
    const parts = [];
    let size = 0;
    for await (const part of req) {
      size += part.length;
      if (size > maxBytes) {
        res.writeHead(413).end();
        return;
      }
      parts.push(part);
    }
    // Pass the original bytes and signature to n8n's GitHub Trigger for HMAC verification.
    const response = await fetch('http://127.0.0.1:5678' + req.url, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-github-event': event,
        'x-github-delivery': String(req.headers['x-github-delivery'] ?? ''),
        'x-hub-signature-256': signature,
      },
      body: Buffer.concat(parts),
      redirect: 'error',
      signal: AbortSignal.timeout(6000),
    });
    if (response.body) await response.body.cancel();
    res.writeHead(response.status).end();
  } catch {
    if (!res.headersSent) res.writeHead(502).end();
  }
});
gateway.requestTimeout = 10000;
gateway.listen(5680, '127.0.0.1');

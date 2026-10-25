#!/usr/bin/env node
// Minimal MCP-compatible JSON-RPC server over stdio (ESM).
// Exposes one tool: luckyspin.bonusEligibility

import readline from 'node:readline'

const rl = readline.createInterface({ input: process.stdin, output: process.stdout, terminal: false })

function send(id, result, error) {
  const msg = error
    ? { jsonrpc: '2.0', id, error }
    : { jsonrpc: '2.0', id, result };
  process.stdout.write(JSON.stringify(msg) + '\n')
}

function isoDateOnly(d) {
  const yr = d.getUTCFullYear()
  const m = String(d.getUTCMonth() + 1).padStart(2, '0')
  const day = String(d.getUTCDate()).padStart(2, '0')
  return `${yr}-${m}-${day}`
}

function nextMidnightUTC(from) {
  const next = new Date(Date.UTC(from.getUTCFullYear(), from.getUTCMonth(), from.getUTCDate() + 1, 0, 0, 0))
  return next.toISOString()
}

function daysBetweenUTC(a, b) {
  const msPerDay = 24 * 60 * 60 * 1000
  const aDay = Date.UTC(a.getUTCFullYear(), a.getUTCMonth(), a.getUTCDate())
  const bDay = Date.UTC(b.getUTCFullYear(), b.getUTCMonth(), b.getUTCDate())
  return Math.floor((bDay - aDay) / msPerDay)
}

const tools = [
  {
    name: 'luckyspin.bonusEligibility',
    description: 'Check if daily bonus is eligible given lastClaimedAt (ISO date). Returns eligibility, daysSince, nextResetAt (UTC).',
    inputSchema: {
      type: 'object',
      required: ['lastClaimedAt'],
      additionalProperties: false,
      properties: {
        lastClaimedAt: { type: 'string', description: 'ISO date-time of last claim (UTC recommended). Example: 2026-10-06T08:00:00Z' },
        now: { type: 'string', description: 'Optional ISO date-time for current time; defaults to current time.' }
      }
    }
  }
]

function handleToolCall(name, args) {
  if (name !== 'luckyspin.bonusEligibility') {
    return { error: { code: -32601, message: `Unknown tool: ${name}` } }
  }
  if (!args || typeof args.lastClaimedAt !== 'string') {
    return { error: { code: -32602, message: 'Invalid params: lastClaimedAt (ISO string) is required' } }
  }
  const last = new Date(args.lastClaimedAt)
  if (isNaN(last.getTime())) {
    return { error: { code: -32602, message: 'Invalid params: lastClaimedAt is not a valid ISO date' } }
  }
  const now = args.now ? new Date(args.now) : new Date()
  if (isNaN(now.getTime())) {
    return { error: { code: -32602, message: 'Invalid params: now is not a valid ISO date' } }
  }
  const eligible = isoDateOnly(now) !== isoDateOnly(last)
  const daysSince = daysBetweenUTC(last, now)
  const nextResetAt = eligible ? new Date().toISOString() : nextMidnightUTC(last)
  const content = [
    { type: 'json', json: { eligible, daysSince, nextResetAt } }
  ]
  return { result: { content } }
}

rl.on('line', (line) => {
  if (!line.trim()) return
  let msg
  try { msg = JSON.parse(line) } catch (e) {
    // Cannot respond without id; log and ignore.
    return
  }
  const { id, method, params } = msg
  if (!method) {
    return send(id, null, { code: -32600, message: 'Invalid Request' })
  }
  if (method === 'initialize') {
    return send(id, {
      protocolVersion: '1.0',
      serverInfo: { name: 'luckyspin-mcp', version: '0.1.0' },
      capabilities: { tools: {} }
    })
  }
  if (method === 'tools/list') {
    return send(id, { tools })
  }
  if (method === 'tools/call') {
    const name = params?.name
    const args = params?.arguments || {}
    const { result, error } = handleToolCall(name, args)
    return send(id, result, error)
  }
  return send(id, null, { code: -32601, message: `Method not found: ${method}` })
})

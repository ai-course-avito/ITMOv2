-- A name given by people to agents, models, MCP servers and units. Old rows have none (NULL):
-- the API then shows a fallback (see database/models.py).
ALTER TABLE agents ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE models ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE mcp_servers ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE units ADD COLUMN IF NOT EXISTS name TEXT;

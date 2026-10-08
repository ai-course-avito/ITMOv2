-- History of what an agent is: its prompt, model, config and MCP servers. Every
-- change that alters one of them adds a row (see database/mixins/agent_version.py).
CREATE TABLE IF NOT EXISTS agent_versions (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    comment TEXT,
    created_by_unit_id BIGINT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (agent_id, number)
);

-- Version 1 of every existing agent
INSERT INTO agent_versions (agent_id, number, snapshot, comment)
SELECT
    a.id,
    1,
    jsonb_build_object(
        'prompt', a.prompt,
        'model_id', a.model_id,
        'model', m.request_json,
        'config', a.config,
        'mcp_servers', COALESCE((
            SELECT jsonb_agg(jsonb_build_object('id', s.id, 'config', s.config) ORDER BY s.id)
            FROM agent_mcp_servers x JOIN mcp_servers s ON s.id = x.mcp_server_id
            WHERE x.agent_id = a.id
        ), '[]'::jsonb)
    ),
    'initial version'
FROM agents a JOIN models m ON m.id = a.model_id;

-- The version of the agent that produced a message
ALTER TABLE messages ADD COLUMN IF NOT EXISTS agent_version INTEGER;

-- Memory: facts an agent has learned about a user (see the `memory` tool).
CREATE TABLE IF NOT EXISTS memories (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    agent_id BIGINT NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS memories_user_agent_idx ON memories (user_id, agent_id, id DESC);

-- `memory` joins the default tools; agents that still have the old default get it too.
ALTER TABLE agents ALTER COLUMN tools SET DEFAULT ARRAY['rag', 'memory'];
UPDATE agents SET tools = ARRAY['rag', 'memory'] WHERE tools = ARRAY['rag'];

-- Connections between agents: agent1 may call agent2 (the built-in tools list_agents and ask_agent), and the
-- description tells agent1 what agent2 is for. Directed: a connection back is a row of its own.
CREATE TABLE IF NOT EXISTS agent_connections (
    id BIGSERIAL PRIMARY KEY,
    agent1_id BIGINT NOT NULL REFERENCES agents (id) ON DELETE CASCADE, -- the one that calls
    agent2_id BIGINT NOT NULL REFERENCES agents (id) ON DELETE CASCADE, -- the one that is called
    description TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT agent_connections_not_to_itself CHECK (agent1_id <> agent2_id),
    CONSTRAINT agent_connections_once UNIQUE (agent1_id, agent2_id)
);
CREATE INDEX IF NOT EXISTS agent_connections_agent2_idx ON agent_connections (agent2_id);

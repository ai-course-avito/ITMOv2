-- Migration bookkeeping: a single row (id = 1) holding the number of the last
-- applied migration. Created here, in migration 0.
CREATE TABLE IF NOT EXISTS migrations (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    version INTEGER NOT NULL
);

INSERT INTO migrations (id, version) VALUES (1, 0) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS models (
    id BIGSERIAL PRIMARY KEY,
    request_json JSONB NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agents (
    id BIGSERIAL PRIMARY KEY,
    prompt TEXT NOT NULL,
    model_id BIGINT NOT NULL REFERENCES models (id) ON DELETE NO ACTION,
    chat_limit INTEGER DEFAULT 10,
    store_history BOOLEAN NOT NULL DEFAULT TRUE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS units (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT REFERENCES agents (id) ON DELETE NO ACTION,
    ip VARCHAR(16),
    token VARCHAR(64) NOT NULL UNIQUE,
    is_admin BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    unit_id BIGINT REFERENCES units (id) ON DELETE NO ACTION,
    external_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_unit_external_user UNIQUE (unit_id, external_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users (id) ON DELETE CASCADE,
    content JSONB NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rag (
    id BIGSERIAL,
    agent_id BIGINT REFERENCES agents (id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (agent_id, id)  
) PARTITION BY LIST (agent_id);

CREATE INDEX IF NOT EXISTS rag_embedding_idx
ON rag USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS mcp_servers (
    id BIGSERIAL PRIMARY KEY,
    config JSONB NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_mcp_servers (
    agent_id BIGINT NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
    mcp_server_id BIGINT NOT NULL REFERENCES mcp_servers (id) ON DELETE CASCADE,
    PRIMARY KEY (agent_id, mcp_server_id)
);

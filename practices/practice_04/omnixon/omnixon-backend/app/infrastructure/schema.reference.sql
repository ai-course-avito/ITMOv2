-- REFERENCE ONLY: the current state of the database, for developers to read.
-- It is NOT used for migrating. The database is built by applying the files in
-- app/database/migrations/ in order (see PostgresPool.run_migrations).
-- Keep this file in sync when you add a migration.

-- Migration bookkeeping: a single row (id = 1) holding the number of the last
-- applied migration. Created here, in migration 0.
CREATE TABLE IF NOT EXISTS migrations (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    version INTEGER NOT NULL
);

INSERT INTO migrations (id, version) VALUES (1, 0) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS models (
    id BIGSERIAL PRIMARY KEY,
    name TEXT, -- migration 10; NULL on old rows (the API shows a fallback)
    request_json JSONB NOT NULL,
    -- migration 12: how the model is reached
    base_url TEXT,                          -- NULL: OpenRouter
    use_proxy BOOLEAN NOT NULL DEFAULT TRUE, -- false: not through OPENROUTER_PROXY
    api_token TEXT,                         -- NULL: the key of the deployment; never returned by the API
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agents (
    id BIGSERIAL PRIMARY KEY,
    name TEXT, -- migration 10
    prompt TEXT NOT NULL,
    model_id BIGINT NOT NULL REFERENCES models (id) ON DELETE NO ACTION,
    -- migration 4: {"tools": [...], "message_limit": int, "memo_limit": int}
    config JSONB NOT NULL DEFAULT '{"tools": ["rag", "memory"]}',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- migration 11: access is a token of a role, bound to an agent (there are no units)
CREATE TABLE IF NOT EXISTS roles (
    name TEXT PRIMARY KEY,
    rank SMALLINT NOT NULL UNIQUE  -- regular 1, user 2, admin 3, owner 4
);

CREATE TABLE IF NOT EXISTS tokens (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    agent_id BIGINT NOT NULL REFERENCES agents (id) ON DELETE RESTRICT,
    role TEXT NOT NULL REFERENCES roles (name),
    token_sha256 CHAR(64) NOT NULL UNIQUE,  -- only the hash of the secret is stored
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS tokens_agent_idx ON tokens (agent_id);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL REFERENCES agents (id) ON DELETE CASCADE,  -- migration 11 (was unit_id)
    external_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_agent_external_user UNIQUE (agent_id, external_id)
);
-- users found by the start of their external id
CREATE INDEX IF NOT EXISTS users_agent_external_id_prefix_idx ON users (agent_id, external_id text_pattern_ops);

-- migration 13: a user has several chats with an agent, each its own thread of messages
CREATE TABLE IF NOT EXISTS chats (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title TEXT, -- NULL: the start of the first message is taken, else a fallback name
    is_default BOOLEAN NOT NULL DEFAULT FALSE, -- where a request without chat_id goes; at most one per user
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- the latest message
);
CREATE UNIQUE INDEX IF NOT EXISTS chats_one_default_idx ON chats (user_id) WHERE is_default;
CREATE INDEX IF NOT EXISTS chats_user_updated_idx ON chats (user_id, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users (id) ON DELETE CASCADE,
    content JSONB NOT NULL,
    agent_version INTEGER, -- migration 6: the version of the agent that produced it
    chat_id BIGINT NOT NULL REFERENCES chats (id) ON DELETE CASCADE, -- migration 13
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS messages_chat_id_idx ON messages (chat_id, id DESC);

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
    name TEXT, -- migration 10
    config JSONB NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_mcp_servers (
    agent_id BIGINT NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
    mcp_server_id BIGINT NOT NULL REFERENCES mcp_servers (id) ON DELETE CASCADE,
    PRIMARY KEY (agent_id, mcp_server_id)
);

-- migration 3
CREATE TABLE IF NOT EXISTS memories (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    agent_id BIGINT NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS memories_user_agent_idx ON memories (user_id, agent_id, id DESC);

-- migration 6
CREATE TABLE IF NOT EXISTS agent_versions (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    comment TEXT,
    created_by_token_id BIGINT,  -- migration 11 (was created_by_unit_id)
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (agent_id, number)
);

-- migration 7
CREATE INDEX IF NOT EXISTS messages_user_id_idx ON messages (user_id, id DESC);
CREATE INDEX IF NOT EXISTS messages_timestamp_idx ON messages (timestamp);

-- migration 8
ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding vector(1536);


-- migration 11: what the models were used for, per token. Texts are never stored.
CREATE TABLE IF NOT EXISTS usage_logs (
    id BIGSERIAL PRIMARY KEY,
    token_id BIGINT REFERENCES tokens (id) ON DELETE SET NULL,
    token_name TEXT NOT NULL,
    agent_id BIGINT,
    model TEXT NOT NULL,
    kind TEXT NOT NULL,      -- request | stream | auto_memory
    status TEXT NOT NULL,    -- ok | an HTTP status | cancelled
    duration_ms INTEGER NOT NULL,
    input_tokens BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    cost NUMERIC(14, 8),     -- NULL: the provider did not say
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS usage_logs_timestamp_idx ON usage_logs (timestamp);
CREATE INDEX IF NOT EXISTS usage_logs_token_idx ON usage_logs (token_id, timestamp);

-- rows older than USAGE_TTL_DAYS, folded: one per token, month and model; these never expire
CREATE TABLE IF NOT EXISTS usage_monthly (
    id BIGSERIAL PRIMARY KEY,
    token_id BIGINT REFERENCES tokens (id) ON DELETE SET NULL,
    token_name TEXT NOT NULL,
    month DATE NOT NULL,
    model TEXT NOT NULL,
    requests BIGINT NOT NULL DEFAULT 0,
    errors BIGINT NOT NULL DEFAULT 0,
    input_tokens BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    cost NUMERIC(14, 8) NOT NULL DEFAULT 0,
    duration_ms_sum BIGINT NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS usage_monthly_key ON usage_monthly (token_id, token_name, month, model);

-- migration 14
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

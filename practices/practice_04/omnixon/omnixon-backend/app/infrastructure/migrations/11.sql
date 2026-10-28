-- Units are gone: access is a token of a role, bound to an agent.
--   roles   regular < user < admin < owner
--   tokens  hold only the sha256 of the secret; the secret is shown once, when the token is made
--   users   belong to an agent (they belonged to a unit)
--   usage_* what the models cost, per token (no texts)

CREATE TABLE IF NOT EXISTS roles (
    name TEXT PRIMARY KEY,
    rank SMALLINT NOT NULL UNIQUE
);
INSERT INTO roles (name, rank) VALUES ('regular', 1), ('user', 2), ('admin', 3), ('owner', 4)
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS tokens (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    agent_id BIGINT NOT NULL REFERENCES agents (id) ON DELETE RESTRICT,
    role TEXT NOT NULL REFERENCES roles (name),
    token_sha256 CHAR(64) NOT NULL UNIQUE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    legacy_unit_id BIGINT
);
CREATE INDEX IF NOT EXISTS tokens_agent_idx ON tokens (agent_id);

-- a unit without an agent gets one (the service made it on the first request until now)
DO $$
DECLARE u RECORD; a BIGINT;
BEGIN
    FOR u IN SELECT id FROM units WHERE agent_id IS NULL LOOP
        INSERT INTO agents (prompt, model_id) VALUES ('', 0) RETURNING id INTO a;
        UPDATE units SET agent_id = a WHERE id = u.id;
    END LOOP;
END $$;

-- every unit becomes a token: admin units admin tokens, the others regular ones. The token of INITIAL_API_KEY
-- is made an owner when the service starts.
INSERT INTO tokens (name, agent_id, role, token_sha256, timestamp, legacy_unit_id)
SELECT COALESCE(NULLIF(name, ''), 'unit ' || id),
       agent_id,
       CASE WHEN is_admin THEN 'admin' ELSE 'regular' END,
       encode(sha256(convert_to(token, 'UTF8')), 'hex'),
       timestamp,
       id
FROM units;

-- users: from a unit to its agent; the users of units that shared an agent are merged by external id
ALTER TABLE users ADD COLUMN IF NOT EXISTS agent_id BIGINT REFERENCES agents (id) ON DELETE CASCADE;
UPDATE users SET agent_id = (SELECT agent_id FROM units WHERE units.id = users.unit_id);
DELETE FROM users WHERE agent_id IS NULL;

WITH ranked AS (
    SELECT id, MIN(id) OVER (PARTITION BY agent_id, external_id) AS keep FROM users
)
UPDATE messages m SET user_id = r.keep FROM ranked r WHERE m.user_id = r.id AND r.id <> r.keep;
WITH ranked AS (
    SELECT id, MIN(id) OVER (PARTITION BY agent_id, external_id) AS keep FROM users
)
UPDATE memories m SET user_id = r.keep FROM ranked r WHERE m.user_id = r.id AND r.id <> r.keep;
DELETE FROM users u USING (
    SELECT id, MIN(id) OVER (PARTITION BY agent_id, external_id) AS keep FROM users
) r WHERE u.id = r.id AND r.id <> r.keep;

DROP INDEX IF EXISTS users_unit_external_id_prefix_idx;
ALTER TABLE users DROP CONSTRAINT IF EXISTS unique_unit_external_user;
ALTER TABLE users DROP COLUMN unit_id;
ALTER TABLE users ALTER COLUMN agent_id SET NOT NULL;
ALTER TABLE users ADD CONSTRAINT unique_agent_external_user UNIQUE (agent_id, external_id);
CREATE INDEX IF NOT EXISTS users_agent_external_id_prefix_idx ON users (agent_id, external_id text_pattern_ops);

-- who made a version: a token now
ALTER TABLE agent_versions ADD COLUMN IF NOT EXISTS created_by_token_id BIGINT;
UPDATE agent_versions v SET created_by_token_id = t.id FROM tokens t WHERE t.legacy_unit_id = v.created_by_unit_id;
ALTER TABLE agent_versions DROP COLUMN created_by_unit_id;

ALTER TABLE tokens DROP COLUMN legacy_unit_id;
DROP TABLE units;

-- what the models were used for, per token. Texts are never stored. The token may be deleted later: the row stays,
-- with the name it had.
CREATE TABLE IF NOT EXISTS usage_logs (
    id BIGSERIAL PRIMARY KEY,
    token_id BIGINT REFERENCES tokens (id) ON DELETE SET NULL,
    token_name TEXT NOT NULL,
    agent_id BIGINT,
    model TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    input_tokens BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    cost NUMERIC(14, 8),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS usage_logs_timestamp_idx ON usage_logs (timestamp);
CREATE INDEX IF NOT EXISTS usage_logs_token_idx ON usage_logs (token_id, timestamp);

-- the old rows of usage_logs, folded: one row per token, month and model. These do not expire.
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
-- a deleted token keeps its rows (token_id NULL); those are never merged with each other, NULLs being distinct
CREATE UNIQUE INDEX IF NOT EXISTS usage_monthly_key ON usage_monthly (token_id, token_name, month, model);

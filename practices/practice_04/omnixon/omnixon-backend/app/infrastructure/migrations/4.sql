-- One JSON with the settings of an agent instead of separate columns:
--   {"tools": [...], "message_limit": <int>, "memo_limit": <int>}
-- Only "tools" is always present; a missing limit means the DEFAULT_* env value.
ALTER TABLE agents ADD COLUMN IF NOT EXISTS config JSONB NOT NULL DEFAULT '{"tools": ["rag", "memory"]}';

UPDATE agents
SET config = jsonb_strip_nulls(jsonb_build_object(
    'tools', to_jsonb(tools),
    'message_limit', CASE WHEN chat_limit IS DISTINCT FROM 10 THEN chat_limit END
));

ALTER TABLE agents DROP COLUMN tools, DROP COLUMN chat_limit;

-- The history is no longer an agent setting: it is chosen per request
-- (`use_memo` / `save_message`).
ALTER TABLE agents DROP COLUMN IF EXISTS store_history;

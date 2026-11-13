-- Chats: a user has several conversations with an agent, and each is its own thread of messages (the model sees the messages of the chat it is
-- asked in; what it remembers about the user, the memories, is shared by all of them).
--   chats.is_default  the chat a request without chat_id goes to (bots do not know about chats); at most one per user
--   every message belongs to a chat: the messages that were there go into the default chat of their user
CREATE TABLE IF NOT EXISTS chats (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title TEXT, -- NULL: the start of the first message is taken when there is one, else a fallback name
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- the latest message
);
CREATE UNIQUE INDEX IF NOT EXISTS chats_one_default_idx ON chats (user_id) WHERE is_default;
CREATE INDEX IF NOT EXISTS chats_user_updated_idx ON chats (user_id, updated_at DESC, id DESC);

ALTER TABLE messages ADD COLUMN IF NOT EXISTS chat_id BIGINT REFERENCES chats (id) ON DELETE CASCADE;

INSERT INTO chats (user_id, is_default, timestamp, updated_at)
SELECT user_id, TRUE, min(timestamp), max(timestamp) FROM messages WHERE user_id IS NOT NULL GROUP BY user_id
ON CONFLICT DO NOTHING;

UPDATE messages m SET chat_id = c.id FROM chats c WHERE c.user_id = m.user_id AND c.is_default AND m.chat_id IS NULL;
DELETE FROM messages WHERE chat_id IS NULL; -- messages of no user: nobody can read them

ALTER TABLE messages ALTER COLUMN chat_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS messages_chat_id_idx ON messages (chat_id, id DESC);

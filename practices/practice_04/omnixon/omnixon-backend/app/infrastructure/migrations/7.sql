-- Indexes for reading a user's latest messages and for expiring old ones
CREATE INDEX IF NOT EXISTS messages_user_id_idx ON messages (user_id, id DESC);
CREATE INDEX IF NOT EXISTS messages_timestamp_idx ON messages (timestamp);

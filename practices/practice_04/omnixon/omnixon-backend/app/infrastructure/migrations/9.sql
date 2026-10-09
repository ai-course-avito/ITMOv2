-- Finding the users of a unit by the start of their external id (the suggestions of the admin panel)
CREATE INDEX IF NOT EXISTS users_unit_external_id_prefix_idx ON users (unit_id, external_id text_pattern_ops);

-- Built-in tools enabled for an agent (see ai/tools.py).
ALTER TABLE agents ADD COLUMN IF NOT EXISTS tools TEXT[] NOT NULL DEFAULT ARRAY['rag'];

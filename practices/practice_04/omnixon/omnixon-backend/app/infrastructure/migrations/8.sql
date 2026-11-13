-- Embeddings of memories, for semantic recall and for recognising a fact that is
-- already remembered. NULL for memories made before (they are filled in at start).
ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding vector(1536);

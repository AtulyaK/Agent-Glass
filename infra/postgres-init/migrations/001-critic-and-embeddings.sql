-- Migration: 001 — critic_decisions and embeddings schema upgrades
-- Apply to running Postgres if the volume was created before this migration.
-- Safe to run multiple times (IF NOT EXISTS / column already exists is harmless).

-- Add threat_class and human_note to critic_decisions
ALTER TABLE critic_decisions ADD COLUMN IF NOT EXISTS threat_class TEXT DEFAULT 'none';
ALTER TABLE critic_decisions ADD COLUMN IF NOT EXISTS human_note TEXT;

-- Pin embeddings vector to 1024 dimensions (nvidia/nv-embedqa-e5-v5)
-- NOTE: This will fail if existing rows have different dimensions.
-- If so, truncate the embeddings table first.
ALTER TABLE embeddings ALTER COLUMN vector TYPE VECTOR(1024);

-- Add IVFFlat cosine index for faster k-NN search (run after inserting at least 1 embedding row)
-- CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);

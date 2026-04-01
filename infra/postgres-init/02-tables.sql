CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS events (
  id SERIAL PRIMARY KEY,
  session_id TEXT REFERENCES sessions(session_id),
  turn INT,
  node TEXT,
  event_type TEXT,
  payload JSONB,
  error TEXT,
  latency_ms NUMERIC,
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  input_hash TEXT,
  output_hash TEXT
);

CREATE TABLE IF NOT EXISTS embeddings (
  id SERIAL PRIMARY KEY,
  session_id TEXT,
  event_id INT REFERENCES events(id),
  label TEXT DEFAULT 'historical',
  provider TEXT,
  model TEXT,
  checksum TEXT,
  vector VECTOR(1024),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS critic_decisions (
  id SERIAL PRIMARY KEY,
  session_id TEXT,
  turn INT,
  decision TEXT,
  flag TEXT,
  threat_class TEXT DEFAULT 'none',
  rationale TEXT,
  halt BOOLEAN DEFAULT FALSE,
  human_note TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS synthetic_samples (
  id SERIAL PRIMARY KEY,
  sample_id TEXT UNIQUE,
  source TEXT,
  category TEXT,
  prompt TEXT,
  expected_decision TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Basic vector index placeholder; refine in app once dimension known
CREATE INDEX IF NOT EXISTS idx_embeddings_session ON embeddings(session_id);
CREATE INDEX IF NOT EXISTS idx_events_session_turn ON events(session_id, turn);

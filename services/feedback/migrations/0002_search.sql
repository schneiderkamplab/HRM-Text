-- Account-administered only; no public CRUD or listing endpoint.
CREATE TABLE search_keys (
  key_hash TEXT PRIMARY KEY,
  jina_key TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
  daily_limit INTEGER NOT NULL DEFAULT 100 CHECK (daily_limit BETWEEN 1 AND 10000),
  usage_day TEXT NOT NULL DEFAULT '',
  used INTEGER NOT NULL DEFAULT 0
);

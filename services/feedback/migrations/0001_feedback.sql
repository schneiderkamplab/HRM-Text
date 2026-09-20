CREATE TABLE feedback (
  id TEXT PRIMARY KEY,
  received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  rating TEXT NOT NULL CHECK (rating IN ('up','down')),
  pseudonym TEXT NOT NULL,
  publication INTEGER NOT NULL CHECK (publication IN (0,1)),
  payload TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  review TEXT NOT NULL DEFAULT 'pending' CHECK (review IN ('pending','approved','rejected')),
  CHECK (review != 'approved' OR publication = 1)
);
CREATE INDEX feedback_review ON feedback(review, received_at);
CREATE TABLE daily_admission (day TEXT PRIMARY KEY, submissions INTEGER NOT NULL, bytes INTEGER NOT NULL);
-- Atomic admission bound, including concurrent requests. Idempotent retries don't fire it.
-- Deletions deliberately do not refund admission capacity.
CREATE TRIGGER feedback_admission AFTER INSERT ON feedback BEGIN
  INSERT INTO daily_admission VALUES (date('now'),1,length(CAST(NEW.payload AS BLOB)))
    ON CONFLICT(day) DO UPDATE SET submissions=submissions+1, bytes=bytes+excluded.bytes;
  SELECT RAISE(ABORT, 'daily_limit') FROM daily_admission
    WHERE day=date('now') AND (submissions > 500 OR bytes > 16777216);
END;

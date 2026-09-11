-- One row per visitor per UTC day. visitor is a salted SHA-256 of the date and
-- IP, never the IP itself. The primary key does the deduplication: the Worker
-- inserts with OR IGNORE, so reloads and repeat visits add nothing.
CREATE TABLE IF NOT EXISTS hits (
  day TEXT NOT NULL,
  visitor TEXT NOT NULL,
  PRIMARY KEY (day, visitor)
) WITHOUT ROWID;

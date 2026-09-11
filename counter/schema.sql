-- One row per visitor per UTC day. visitor is a salted SHA-256 of the date and
-- IP, never the IP itself. The primary key keeps a visitor to one row a day;
-- the Worker upserts, so a repeat visit bumps hits instead of adding a row.
CREATE TABLE IF NOT EXISTS hits (
  day TEXT NOT NULL,
  visitor TEXT NOT NULL,
  hits INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (day, visitor)
) WITHOUT ROWID;

-- hits was added on 2026-09-11. A database created before then needs, once:
-- ALTER TABLE hits ADD COLUMN hits INTEGER NOT NULL DEFAULT 1;

-- Durable dataset sessions. The DataFrame itself lives in R2 at
-- sessions/<id>.parquet; these tables hold metadata, the reproducibility
-- log, analysis results, and multi-result share links.
-- Apply with: wrangler d1 migrations apply infera-db --remote

CREATE TABLE data_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    conversation_id TEXT,
    filename TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_used_at TEXT NOT NULL
);

CREATE INDEX idx_data_sessions_conversation_id ON data_sessions(conversation_id);
CREATE INDEX idx_data_sessions_last_used_at ON data_sessions(last_used_at);

CREATE TABLE session_steps (
    session_id TEXT NOT NULL REFERENCES data_sessions(id),
    timestamp REAL NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL
);

CREATE INDEX idx_session_steps_session_id ON session_steps(session_id);

CREATE TABLE session_results (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES data_sessions(id),
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_session_results_session_id ON session_results(session_id);

CREATE TABLE session_share_tokens (
    token TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

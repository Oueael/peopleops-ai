
import os

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL was not found in the .env file."
    )


def get_connection():
    """Create and return a PostgreSQL connection."""

    conn = psycopg.connect(DATABASE_URL)
    register_vector(conn)

    return conn


def initialize_database():
    """Create the application tables if they don't exist."""

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id SERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    section TEXT,
                    content TEXT NOT NULL,
                    audience TEXT DEFAULT 'all_employees',
                    region TEXT DEFAULT 'global',
                    last_updated TEXT,
                    embedding VECTOR(384)
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS assistant_audit_log (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    slack_user_id TEXT,
                    slack_channel_id TEXT,
                    role TEXT NOT NULL,
                    region TEXT NOT NULL,
                    question_hash TEXT NOT NULL,
                    question_length INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    escalation_category TEXT,
                    retrieved_sources JSONB,
                    citation_valid BOOLEAN,
                    abstained BOOLEAN,
                    latency_ms INTEGER
                );
            """)

        conn.commit()


if __name__ == "__main__":
    initialize_database()
    print("Database initialized successfully.")


from rag.database import get_connection


def initialize_feedback_table():
    """Create the feedback table if it doesn't exist."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS assistant_feedback (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    slack_user_id TEXT NOT NULL,
                    slack_channel_id TEXT NOT NULL,
                    message_ts TEXT NOT NULL,
                    rating TEXT NOT NULL
                        CHECK (rating IN ('positive', 'negative')),
                    UNIQUE (slack_user_id, slack_channel_id, message_ts)
                );
            """)
        conn.commit()


def record_feedback(
    slack_user_id,
    slack_channel_id,
    message_ts,
    rating
):
    """Save or update a user's feedback for an assistant answer."""

    if rating not in ("positive", "negative"):
        raise ValueError("Rating must be positive or negative.")

    initialize_feedback_table()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO assistant_feedback (
                    slack_user_id,
                    slack_channel_id,
                    message_ts,
                    rating
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (
                    slack_user_id,
                    slack_channel_id,
                    message_ts
                )
                DO UPDATE SET
                    rating = EXCLUDED.rating,
                    created_at = NOW();
            """, (
                slack_user_id,
                slack_channel_id,
                message_ts,
                rating
            ))
        conn.commit()

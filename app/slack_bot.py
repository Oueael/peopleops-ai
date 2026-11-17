
import os
import re
import logging

from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from rag.generate import generate_answer
from rag.feedback import record_feedback
from app.user_roles import get_user_role
from policy.escalation import detect_escalation


load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_HR_CHANNEL_ID = os.getenv("SLACK_HR_CHANNEL_ID")

if not SLACK_BOT_TOKEN:
    raise ValueError("SLACK_BOT_TOKEN was not found in .env")

if not SLACK_APP_TOKEN:
    raise ValueError("SLACK_APP_TOKEN was not found in .env")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger(__name__)

app = App(token=SLACK_BOT_TOKEN)

executor = ThreadPoolExecutor(max_workers=4)


def feedback_blocks(answer):
    """Create Slack feedback buttons."""

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": answer
            }
        },
        {
            "type": "actions",
            "block_id": "assistant_feedback",
            "elements": [
                {
                    "type": "button",
                    "action_id": "feedback_positive",
                    "text": {
                        "type": "plain_text",
                        "text": "Helpful"
                    },
                    "style": "primary",
                    "value": "positive"
                },
                {
                    "type": "button",
                    "action_id": "feedback_negative",
                    "text": {
                        "type": "plain_text",
                        "text": "Not helpful"
                    },
                    "value": "negative"
                }
            ]
        }
    ]


def notify_hr(client, user_id, category):
    """Send a minimal sensitive-issue notification to the private HR channel."""

    if not SLACK_HR_CHANNEL_ID:
        logger.error(
            "HR escalation detected, but SLACK_HR_CHANNEL_ID is not configured."
        )
        return

    message = (
        ":warning: *People Operations escalation received*\n"
        f"*Category:* {category.replace('_', ' ').title()}\n"
        f"*Reporting employee:* <@{user_id}>\n"
        "Please follow up with the employee directly through a private conversation."
    )

    try:
        client.chat_postMessage(
            channel=SLACK_HR_CHANNEL_ID,
            text=message
        )

        logger.info(
            "HR notification sent for user %s, category %s",
            user_id,
            category
        )

    except Exception:
        logger.exception(
            "Failed to send HR escalation notification for user %s",
            user_id
        )


def process_question(
    client,
    question,
    user_id,
    role,
    response_channel,
    audit_channel,
    placeholder_ts
):
    """Generate an answer and update the user's private DM."""

    try:
        escalation = detect_escalation(question)

        answer = generate_answer(
            question,
            role=role,
            region="US",
            request_context={
                "user_id": user_id,
                "channel_id": audit_channel
            }
        )

        # Escalation responses should not include feedback buttons.
        if escalation["escalate"]:
            client.chat_update(
                channel=response_channel,
                ts=placeholder_ts,
                text=answer,
                blocks=[]
            )
        else:
            client.chat_update(
                channel=response_channel,
                ts=placeholder_ts,
                text=answer,
                blocks=feedback_blocks(answer)
            )

        logger.info(
            "Successfully answered Slack question from %s with role %s",
            user_id,
            role
        )

        # Notify HR separately when a sensitive topic is detected.
        if escalation["escalate"]:
            notify_hr(
                client,
                user_id,
                escalation["category"]
            )

    except Exception:
        logger.exception(
            "Failed to process Slack question from %s",
            user_id
        )

        try:
            client.chat_update(
                channel=response_channel,
                ts=placeholder_ts,
                text=(
                    "I encountered an error while processing "
                    "your question. Please try again."
                ),
                blocks=[]
            )
        except Exception:
            logger.exception("Failed to update private error message.")


@app.event("app_mention")
def handle_mention(event, client, logger):
    """Receive a public mention but deliver the answer privately."""

    channel = event["channel"]
    user_id = event.get("user")

    if not user_id:
        logger.warning("Slack mention did not contain a user ID.")
        return

    question = re.sub(
        r"<@[A-Z0-9]+>",
        "",
        event.get("text", "")
    ).strip()

    role = get_user_role(user_id)

    logger.info(
        "Received Slack question from user %s with role %s",
        user_id,
        role
    )

    if not question:
        client.chat_postEphemeral(
            channel=channel,
            user=user_id,
            text="Hi! What would you like to know about company policies?"
        )
        return

    # Acknowledge the mention privately in the original channel.
    client.chat_postEphemeral(
        channel=channel,
        user=user_id,
        text="I'll look that up and send the answer to you in a direct message."
    )

    try:
        # Open a one-to-one conversation with the requesting user.
        dm_response = client.conversations_open(
            users=user_id
        )

        response_channel = dm_response["channel"]["id"]

        # Create the placeholder in the private conversation.
        placeholder = client.chat_postMessage(
            channel=response_channel,
            text="I'm looking that up. I'll reply here when I have an answer..."
        )

        placeholder_ts = placeholder["ts"]

    except Exception:
        logger.exception(
            "Could not open a private Slack conversation for %s",
            user_id
        )

        # Never publish the answer in the original public channel.
        client.chat_postEphemeral(
            channel=channel,
            user=user_id,
            text=(
                "I couldn't open a private conversation with you. "
                "Please contact the People Operations team."
            )
        )
        return

    executor.submit(
        process_question,
        client,
        question,
        user_id,
        role,
        response_channel,
        channel,
        placeholder_ts
    )


@app.action("feedback_positive")
@app.action("feedback_negative")
def handle_feedback(ack, body, client, logger):
    """Save feedback when a Slack button is clicked."""

    ack()

    user_id = body["user"]["id"]
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    action = body["actions"][0]
    rating = action["value"]

    try:
        record_feedback(
            slack_user_id=user_id,
            slack_channel_id=channel,
            message_ts=message_ts,
            rating=rating
        )

        logger.info(
            "Received %s feedback from user %s",
            rating,
            user_id
        )

        confirmation = "Thanks! Your feedback was recorded."

    except Exception:
        logger.exception("Failed to save Slack feedback.")

        confirmation = (
            "Sorry, I couldn't save your feedback. Please try again."
        )

    client.chat_postEphemeral(
        channel=channel,
        user=user_id,
        text=confirmation
    )


if __name__ == "__main__":
    logger.info("Starting PeopleOps Assistant Slack bot...")

    handler = SocketModeHandler(
        app,
        SLACK_APP_TOKEN
    )

    handler.start()

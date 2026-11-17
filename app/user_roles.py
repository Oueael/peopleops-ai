
import os

from dotenv import load_dotenv

load_dotenv()


def get_user_role(slack_user_id):
    """Return a role based on trusted Slack user ID configuration."""

    manager_ids = {
        user_id.strip()
        for user_id in os.getenv("SLACK_MANAGER_IDS", "").split(",")
        if user_id.strip()
    }

    hr_ids = {
        user_id.strip()
        for user_id in os.getenv("SLACK_HR_IDS", "").split(",")
        if user_id.strip()
    }

    if slack_user_id in hr_ids:
        return "hr"

    if slack_user_id in manager_ids:
        return "manager"

    return "employee"

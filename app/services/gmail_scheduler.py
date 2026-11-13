
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.routers.gmail import process_gmail_emails
from app.services import gmail_service


logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(
    timezone="Asia/Kolkata"
)


def monitor_gmail():
    """Check Gmail and process new labelled emails."""

    if not gmail_service.TOKEN_PATH.exists():
        logger.info("Gmail is not connected. Skipping automatic check.")
        return

    try:
        logger.info("Starting automatic Gmail check...")

        result = process_gmail_emails(max_results=10)

        logger.info(
            "Gmail check completed. Found: %s, Processed: %s, Skipped: %s",
            result["total_emails_found"],
            result["processed"],
            result["skipped"]
        )

    except Exception:
        logger.exception("Automatic Gmail processing failed.")


def start_gmail_scheduler():
    """Start checking Gmail every 60 seconds."""

    if not scheduler.running:
        scheduler.add_job(
            monitor_gmail,
            trigger="interval",
            seconds=60,
            id="automatic_gmail_monitor",
            replace_existing=True,
            max_instances=1,
            coalesce=True
        )

        scheduler.start()

        logger.info("Gmail scheduler started. Checking every 60 seconds.")


def stop_gmail_scheduler():
    """Stop the Gmail scheduler safely."""

    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Gmail scheduler stopped.")


from datetime import date, datetime
from dateutil import parser


def normalize_date(value):
    """
    Convert common date formats into YYYY-MM-DD.
    Supports date objects, timestamps and human-readable dates.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    value = str(value).strip()

    if not value:
        return None

    try:
        # fuzzy=True allows text such as:
        # "Due date: 27 November 2026"
        parsed = parser.parse(
            value,
            fuzzy=True,
            dayfirst=True
        )
        return parsed.date()

    except (ValueError, TypeError, OverflowError):
        return None


def check_payment_due_date(due_date):
    """
    Check payment status using flexible date parsing.
    """

    due = normalize_date(due_date)

    if due is None:
        return {
            "status": "Needs Review",
            "message": (
                "Could not recognize the due date. "
                "Please verify the date in the original invoice."
            )
        }

    today = date.today()
    difference = (due - today).days

    if difference < 0:
        return {
            "status": "Overdue",
            "days_overdue": abs(difference),
            "message": (
                f"Payment is overdue by {abs(difference)} days."
            )
        }

    elif difference == 0:
        return {
            "status": "Due Today",
            "days_remaining": 0,
            "message": "Payment is due today."
        }

    else:
        return {
            "status": "Upcoming",
            "days_remaining": difference,
            "message": (
                f"Payment is due in {difference} days."
            )
        }

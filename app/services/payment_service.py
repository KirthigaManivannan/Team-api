
from datetime import date


def check_payment_due_date(due_date):
    """
    Check the payment status based on invoice due date.
    """

    try:
        due = date.fromisoformat(due_date)
    except (ValueError, TypeError):
        return {
            "status": "Invalid Date",
            "message": "Please provide a valid due date in YYYY-MM-DD format."
        }

    today = date.today()
    difference = (due - today).days

    if difference < 0:
        return {
            "status": "Overdue",
            "days_overdue": abs(difference),
            "message": f"Payment is overdue by {abs(difference)} days."
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
            "message": f"Payment is due in {difference} days."
        }
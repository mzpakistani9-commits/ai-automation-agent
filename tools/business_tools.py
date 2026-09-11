"""Business tools for the AI automation agent — the same ones I run in my practice.

Real integrations activate when the corresponding env var is set:
  SLACK_WEBHOOK_URL → Slack webhook POST
  RESEND_API_KEY    → Resend transactional email API
Otherwise both tools queue to a local JSON outbox (honest offline demo).
"""

import json
import os
from datetime import datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.stores import CRMStore, CalendarStore, OutboxStore
from tools.registry import Tool

calendar = CalendarStore()
crm = CRMStore()
outbox = OutboxStore()


def _check_availability(**kw):
    date = kw.get("date", "")
    if date:
        return {"ok": True, "date": date, "available": calendar.available(date)}
    schedule = {}
    for d, slots in calendar.data.items():
        if slots.get("open"):
            schedule[d] = slots["open"]
    return {"ok": True, "date": "next available days", "available": schedule}


def _book_session(**kw):
    date = kw.get("date", "")
    time = kw.get("time", "")
    contact = kw.get("contact", "") or kw.get("name", "")
    if not (date and time and contact):
        return {"ok": False, "error": "date, time and contact name are required"}
    return calendar.book(date, time, contact)


def _list_bookings(**kw):
    return {"ok": True, "bookings": calendar.upcoming()}


def _upsert_contact(**kw):
    return crm.upsert({
        "name": kw.get("name"),
        "email": kw.get("email"),
        "phone": kw.get("phone"),
        "company": kw.get("company"),
        "stage": kw.get("stage"),
        "notes": kw.get("notes"),
    })


def _lookup_faq(**kw):
    query = kw.get("query", "")
    faq = {
        "session length": "Standard sessions are 50 minutes. Intake sessions run 75 minutes.",
        "cancel": "You can reschedule or cancel up to 24 hours before your session at no charge.",
        "insurance": "We do not bill insurance directly, but we provide a receipt you can submit.",
        "emergency": "If this is an emergency, call 911 or go to the nearest emergency room.",
        "online": "Sessions are offered both in person and via secure video link.",
        "cost": "An initial consultation is Rs 4,500 and standard sessions are Rs 4,000.",
    }
    q = query.lower()
    for key, answer in faq.items():
        if key in q:
            return {"ok": True, "answer": answer, "matched": key}
    return {"ok": False, "answer": "I don't have a confident answer for that.", "matched": None}


def _send_confirmation(**kw):
    to = kw.get("to", "")
    date = kw.get("date", "")
    time = kw.get("time", "")
    if not to:
        return {"ok": False, "error": "recipient (to) is required"}
    subject = f"Session confirmation — {date} at {time}"
    body = f"Your session is confirmed for {date} at {time}. Reply to reschedule up to 24h ahead."
    return outbox.queue(to, subject, body)


# --- Slack / email helpers (JSON outbox in offline mode, real HTTP when keys are set) ---


def _queue_slack(channel: str, message: str) -> dict:
    path = settings.slack_outbox_path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = json.load(open(path)) if os.path.exists(path) else {"messages": []}
    record = {"channel": channel, "message": message, "queued_at": str(datetime.now())}
    data["messages"].append(record)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return {"ok": True, "queued": True, "channel": channel}


def _queue_email(to: str, subject: str, body: str) -> dict:
    path = settings.email_outbox_path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = json.load(open(path)) if os.path.exists(path) else {"messages": []}
    record = {"to": to, "subject": subject, "body": body, "from": settings.resend_from, "queued_at": str(datetime.now())}
    data["messages"].append(record)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return {"ok": True, "queued": True, "to": to, "subject": subject}


def _notify_slack(**kw):
    message = kw.get("message", "")
    channel = kw.get("channel", "#general")
    if not message:
        return {"ok": False, "error": "message is required"}
    if settings.slack_webhook_url:
        try:
            req = Request(
                settings.slack_webhook_url,
                data=json.dumps({"text": message, "channel": channel}).encode(),
                headers={"Content-Type": "application/json"},
            )
            resp = urlopen(req, timeout=10)
            return {"ok": True, "sent": True, "channel": channel, "status": resp.status}
        except (URLError, OSError) as exc:
            return {"ok": False, "error": f"Slack send failed: {exc}"}
    return _queue_slack(channel, message)


def _send_email(**kw):
    to = kw.get("to", "")
    subject = kw.get("subject", "")
    body = kw.get("body", "")
    if not (to and subject and body):
        return {"ok": False, "error": "to, subject and body are required"}
    if settings.resend_api_key:
        try:
            payload = json.dumps({
                "from": settings.resend_from,
                "to": [to],
                "subject": subject,
                "text": body,
            }).encode()
            req = Request(
                "https://api.resend.com/emails",
                data=payload,
                headers={"Authorization": f"Bearer {settings.resend_api_key}", "Content-Type": "application/json"},
            )
            resp = urlopen(req, timeout=10)
            data = json.loads(resp.read())
            return {"ok": True, "sent": True, "to": to, "id": data.get("id")}
        except (URLError, OSError) as exc:
            return {"ok": False, "error": f"Email send failed: {exc}"}
    return _queue_email(to, subject, body)


def build_toolbox():
    return [
        Tool(
            name="check_availability",
            description="List free time slots for a given date (YYYY-MM-DD).",
            parameters={
                "date": {"type": "string", "description": "Date to check, format YYYY-MM-DD"}
            },
            handler=_check_availability,
        ),
        Tool(
            name="book_session",
            description="Book a therapy session slot for a client.",
            parameters={
                "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                "time": {"type": "string", "description": "Slot time like 10:00"},
                "contact": {"type": "string", "description": "Client name or contact"},
            },
            handler=_book_session,
        ),
        Tool(
            name="list_bookings",
            description="List all upcoming booked sessions.",
            parameters={},
            handler=_list_bookings,
        ),
        Tool(
            name="upsert_contact",
            description="Create or update a client/lead in the CRM.",
            parameters={
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "company": {"type": "string"},
                "stage": {"type": "string"},
                "notes": {"type": "string"},
            },
            handler=_upsert_contact,
        ),
        Tool(
            name="lookup_faq",
            description="Answer a common question using the practice knowledge base.",
            parameters={"query": {"type": "string", "description": "The user's question"}},
            handler=_lookup_faq,
        ),
        Tool(
            name="send_confirmation",
            description="Queue a session-confirmation email to the client after a booking.",
            parameters={
                "to": {"type": "string", "description": "Recipient (client name or email)"},
                "date": {"type": "string", "description": "Scheduled date YYYY-MM-DD"},
                "time": {"type": "string", "description": "Scheduled time like 10:00"},
            },
            handler=_send_confirmation,
        ),
        Tool(
            name="notify_slack",
            description="Send a Slack message to a channel (e.g. new lead, booking, alert).",
            parameters={
                "message": {"type": "string", "description": "Message text to post"},
                "channel": {"type": "string", "description": "Slack channel like #general or #leads"},
            },
            handler=_notify_slack,
        ),
        Tool(
            name="send_email",
            description="Send a general email (not the confirmation) to any recipient.",
            parameters={
                "to": {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            handler=_send_email,
        ),
    ]


def toolbox_json():
    from tools.registry import Toolbox

    return Toolbox(build_toolbox())
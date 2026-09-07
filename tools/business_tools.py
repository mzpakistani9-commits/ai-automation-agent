"""Business tools for the AI automation agent — the same ones I run in my practice."""

import json

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
    ]


def toolbox_json():
    from tools.registry import Toolbox

    return Toolbox(build_toolbox())
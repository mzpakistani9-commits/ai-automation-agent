import json
import os
from typing import List

from .config import settings


class CalendarStore:
    DEFAULTS = {
        "2026-09-14": ["10:00", "11:00", "12:00", "15:00", "16:00"],
        "2026-09-15": ["10:00", "11:00", "14:00", "15:00"],
        "2026-09-16": ["09:00", "10:00", "12:00", "13:00"],
    }

    def __init__(self, path: str = settings.calendar_path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        if os.path.exists(path):
            self.data = json.load(open(path))
        else:
            self.data = {d: {"open": times, "booked": []} for d, times in self.DEFAULTS.items()}
            self._persist()

    def _persist(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def available(self, date: str) -> List[str]:
        slots = self.data.get(date, {})
        return slots.get("open", [])

    def book(self, date: str, time: str, contact: str) -> dict:
        slots = self.data.setdefault(date, {"open": [], "booked": []})
        if time not in slots["open"]:
            return {"ok": False, "reason": f"{date} {time} is not available"}
        slots["open"].remove(time)
        slots["booked"].append({"time": time, "contact": contact})
        self._persist()
        return {"ok": True, "date": date, "time": time, "contact": contact}

    def upcoming(self) -> List[dict]:
        booked = []
        for date, slots in self.data.items():
            for b in slots.get("booked", []):
                booked.append({"date": date, **b})
        return sorted(booked, key=lambda b: b["date"])


class CRMStore:
    def __init__(self, path: str = settings.crm_path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.data = {"contacts": []}
        if os.path.exists(path):
            self.data = json.load(open(path))

    def _persist(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def upsert(self, contact: dict) -> dict:
        key = (contact.get("email") or "").lower() or (contact.get("phone") or f"contact-{len(self.data['contacts'])}")
        for c in self.data["contacts"]:
            ckey = (c.get("email") or "").lower() or (c.get("phone") or "")
            if ckey == key and key:
                c.update({k: v for k, v in contact.items() if v is not None})
                self._persist()
                return {"ok": True, "action": "updated", "contact": c}
        record = {**contact, "stage": contact.get("stage", "lead"), "created_at": str(__import__("datetime").datetime.now())}
        self.data["contacts"].append(record)
        self._persist()
        return {"ok": True, "action": "created", "contact": record}

class OutboxStore:
    """Queries confirmation emails for a booking. Demo outbox: writes a JSON
    message record instead of SMTP so it runs honestly with no credentials."""

    def __init__(self, path: str = settings.outbox_path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.data = {"messages": []}
        if os.path.exists(path):
            self.data = json.load(open(path))

    def _persist(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def queue(self, to: str, subject: str, body: str) -> dict:
        record = {
            "to": to,
            "subject": subject,
            "body": body,
            "queued_at": str(__import__("datetime").datetime.now()),
        }
        self.data["messages"].append(record)
        self._persist()
        return {"ok": True, "queued": True, "to": to, "subject": subject}

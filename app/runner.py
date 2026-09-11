"""Agent orchestrator — LLM function-calling loop with a deterministic offline fallback.

Works with a real OpenAI key, or with AGENT_PROVIDER=local (no key) using a
keyword-routing fallback. Every turn is appended to a run transcript.
"""

import json
import os
import re
import time
from typing import Dict, List

from app.config import settings
from tools.registry import Toolbox


class Runner:
    def __init__(self, toolbox: Toolbox):
        self.toolbox = toolbox

    def run(self, user_message: str, run_id: str | None = None) -> Dict:
        run_id = run_id or f"run-{int(time.time() * 1000)}"
        transcript = []
        if settings.provider == "local" or not settings.openai_api_key:
            result = self._run_local(user_message, transcript)
        else:
            result = self._run_llm(user_message, transcript)
        payload = {
            "run_id": run_id,
            "user_message": user_message,
            "transcript": transcript,
            "final_answer": result,
            "provider": settings.provider if settings.openai_api_key else "local",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._save(run_id, payload)
        return payload

    def _run_local(self, message: str, transcript: List) -> str:
        transcript.append({"role": "user", "content": message})
        intent = self._classify(message)
        if intent == "book":
            return self._book_flow(message, transcript)
        if intent == "availability":
            tool_out = self.toolbox.execute("check_availability", json.dumps({}))
            transcript.append({"role": "tool", "name": "check_availability", "output": tool_out})
            return f"Here are the slots I have available.\n{tool_out}"
        if intent == "faq":
            tool_out = self.toolbox.execute("lookup_faq", json.dumps({"query": message}))
            transcript.append({"role": "tool", "name": "lookup_faq", "output": tool_out})
            data = json.loads(tool_out)
            return data.get("answer") or "I couldn't find a confident answer."
        if intent == "bookings":
            tool_out = self.toolbox.execute("list_bookings", json.dumps({}))
            transcript.append({"role": "tool", "name": "list_bookings", "output": tool_out})
            return f"Here are your upcoming bookings.\n{tool_out}"
        if intent == "slack":
            msg = self._extract_after(message, ("slack", "channel", "post to", "notify"))
            tool_out = self.toolbox.execute("notify_slack", json.dumps({"message": msg}))
            transcript.append({"role": "tool", "name": "notify_slack", "output": tool_out})
            return f"Slack message posted.\n{tool_out}"
        if intent == "email":
            subj_m = re.search(r"(?:subject|about)\s+['\"]?([^'\"]+)", message, re.IGNORECASE)
            to_m = re.search(r"to\s+([\w.+-]+@[\w-]+\.[\w.]+)", message)
            subject = subj_m.group(1).strip() if subj_m else "Agent notification"
            to = to_m.group(1) if to_m else ""
            tool_out = self.toolbox.execute(
                "send_email", json.dumps({"to": to, "subject": subject, "body": message})
            )
            transcript.append({"role": "tool", "name": "send_email", "output": tool_out})
            return f"Email queued.\n{tool_out}"
        return "I can help you check availability, book a session, or answer common questions. Try: 'I want to book a session'."

    def _book_flow(self, message: str, transcript: List) -> str:
        date_m = re.search(r"\d{4}-\d{2}-\d{2}", message)
        time_m = re.search(r"\b(\d{1,2}):00\b", message)
        if not (date_m and time_m):
            tool_out = self.toolbox.execute("check_availability", json.dumps({}))
            transcript.append({"role": "tool", "name": "check_availability", "output": tool_out})
            return (f"I can book a session for you. Please give me a date and time. "
                    f"Available slots: {tool_out}")
        date, time = date_m.group(0), time_m.group(1).zfill(2) + ":00"
        avail = self.toolbox.execute("check_availability", json.dumps({"date": date}))
        transcript.append({"role": "tool", "name": "check_availability", "output": avail})
        if time not in json.loads(avail).get("available", []):
            return f"Sorry, {time} on {date} is not free. Check availability and pick another slot: {avail}"
        name_m = re.search(r"(?:for|for me|name is|i'm|i am)\s+([\w\s]+?)(?=\s+on\s+\d{4}|\s+at\s+\d|$)", message)
        contact = name_m.group(1).strip() if name_m else "Client"
        book = self.toolbox.execute("book_session", json.dumps({"date": date, "time": time, "contact": contact}))
        transcript.append({"role": "tool", "name": "book_session", "output": book})
        crm = self.toolbox.execute("upsert_contact", json.dumps({"name": contact, "stage": "booked"}))
        transcript.append({"role": "tool", "name": "upsert_contact", "output": crm})
        confirm = self.toolbox.execute(
            "send_confirmation", json.dumps({"to": contact, "date": date, "time": time})
        )
        transcript.append({"role": "tool", "name": "send_confirmation", "output": confirm})
        data = json.loads(book)
        return (
            f"Booked! Your session is {data['time']} on {data['date']}. "
            f"A confirmation email is queued for {contact}."
        )

    def _run_llm(self, message: str, transcript: List) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI automation assistant for a therapy practice. You can call tools "
                    "to check availability, book sessions, list bookings, upsert CRM contacts, queue "
                    "confirmation emails, send general emails, post to Slack, and answer FAQ "
                    "questions. Prefer calling tools instead of guessing. Be concise."
                ),
            },
            {"role": "user", "content": message},
        ]
        transcript.append({"role": "user", "content": message})
        tools = self.toolbox.schemas()
        for _ in range(settings.max_steps):
            resp = client.chat.completions.create(
                model=settings.openai_model, messages=messages, tools=tools, temperature=0
            )
            choice = resp.choices[0]
            if getattr(choice.message, "tool_calls", None):
                messages.append(choice.message.model_dump(exclude_none=True))
                for tc in choice.message.tool_calls:
                    transcript.append({"role": "tool", "name": tc.function.name, "arguments": tc.function.arguments})
                    output = self.toolbox.execute(tc.function.name, tc.function.arguments)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": output})
                continue
            answer = choice.message.content or ""
            transcript.append({"role": "assistant", "content": answer})
            return answer
        return "I ran out of steps before completing that. Try again."

    @staticmethod
    def _classify(message: str) -> str:
        m = message.lower()
        if any(k in m for k in ("bookings", "upcoming", "my sessions", "list bookings")):
            return "bookings"
        if "slack" in m or "post to channel" in m or "notify" in m:
            return "slack"
        if "email" in m or "send mail" in m or "drop an email" in m:
            return "email"
        if "book" in m or "schedule" in m or "appointment" in m:
            return "book"
        if "availab" in m or "slot" in m or "when" in m or "free" in m:
            return "availability"
        if any(k in m for k in ("cost", "cancel", "insurance", "online", "emergency", "length", "long", "fee")):
            return "faq"
        return "fallback"

    @staticmethod
    def _extract_after(message: str, keys: tuple) -> str:
        lower = message.lower()
        for key in keys:
            idx = lower.find(key)
            if idx != -1:
                candidate = message[idx + len(key) :].strip(" :,;-\"'")
                if candidate:
                    return candidate
        return message

    def _save(self, run_id: str, payload: Dict):
        os.makedirs(settings.runs_dir, exist_ok=True)
        with open(os.path.join(settings.runs_dir, f"{run_id}.json"), "w") as f:
            json.dump(payload, f, indent=2)
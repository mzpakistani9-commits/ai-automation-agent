import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("RUNS_DIR", "/tmp/agent_test_runs")
os.environ.setdefault("CRM_PATH", "/tmp/agent_test_crm.json")
os.environ.setdefault("CALENDAR_PATH", "/tmp/agent_test_calendar.json")

from tools.registry import Toolbox
from tools.business_tools import build_toolbox
from app.runner import Runner
from app.stores import CalendarStore, CRMStore

toolbox = Toolbox(build_toolbox())
runner = Runner(toolbox)


def test_toolbox_contains_business_tools():
    for name in ("check_availability", "book_session", "list_bookings", "upsert_contact", "lookup_faq"):
        assert name in toolbox


def test_schemas_are_function_type():
    for schema in toolbox.schemas():
        assert schema["type"] == "function"
        assert "name" in schema["function"]


def test_unknown_tool_returns_error():
    out = toolbox.execute("does_not_exist", "{}")
    assert "error" in out


def test_book_session_updates_calendar():
    result = toolbox.execute("book_session", '{"date":"2026-09-14","time":"10:00","contact":"Sara"}')
    assert '"ok": true' in result
    cal = CalendarStore("/tmp/agent_test_calendar.json")
    assert "10:00" not in cal.available("2026-09-14")
    assert cal.data["2026-09-14"]["booked"] != []


def test_upsert_contact_creates_and_updates():
    out1 = toolbox.execute("upsert_contact", json_dumps({"name": "Sara", "email": "sara@example.com", "stage": "booked"}))
    assert '"created"' in out1
    out2 = toolbox.execute("upsert_contact", json_dumps({"name": "Sara Khan", "email": "sara@example.com", "stage": "lead"}))
    assert '"updated"' in out2


def test_agent_booking_end_to_end_offline():
    import json

    cal_out = runner.run("I want to book a session on 2026-09-15 at 10:00")
    assert "2026-09-15" in cal_out["final_answer"]
    transcript_roles = [t["role"] for t in cal_out["transcript"]]
    assert "tool" in transcript_roles
    assert cal_out["run_id"].startswith("run-")


def test_agent_availability_flow():
    out = runner.run("what slots are available?")
    assert "Available" in out["final_answer"] or "available" in out["final_answer"]


def test_agent_requests_missing_slot_info():
    out = runner.run("book me a session please")
    assert "Available slots" in out["final_answer"]


def test_lookup_faq_answers_cost():
    out = toolbox.execute("lookup_faq", '{"query":"how much does a session cost?"}')
    assert "Rs 4,000" in out


def json_dumps(d):
    import json

    return json.dumps(d)
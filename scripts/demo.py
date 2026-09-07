"""End-to-end demo: a patient books a session through the agent with a clean run log."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.runner import Runner
from tools.registry import Toolbox
from tools.business_tools import build_toolbox


def main():
    runner = Runner(Toolbox(build_toolbox()))

    convo = [
        "How much does a session cost?",
        "What slots are available?",
        "I want to book a session for Sara on 2026-09-16 at 09:00",
        "Show me my upcoming bookings",
    ]
    for line in convo:
        print(f"\n> {line}")
        result = runner.run(line)
        print(f"< {result['final_answer']}")
        for step in result["transcript"]:
            if step["role"] == "tool":
                print(f"   [tool] {step['name']} -> {step['output'][:110]}")
        print(f"   [saved to runs/{result['run_id']}.json]")


if __name__ == "__main__":
    main()
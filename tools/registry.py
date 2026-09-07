"""Tool registry — every tool declares a JSON schema the LLM can call."""

import json
from dataclasses import dataclass, field
from typing import Callable, Dict, List


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict
    handler: Callable

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                },
            },
        }

    def run(self, json_args: str) -> str:
        try:
            args = json.loads(json_args) if json_args.strip() else {}
            result = self.handler(**args)
            return json.dumps(result)
        except Exception as e:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(e)})


class Toolbox:
    def __init__(self, tools: List[Tool]):
        self._tools: Dict[str, Tool] = {t.name: t for t in tools}

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __getitem__(self, name: str) -> Tool:
        return self._tools[name]

    def execute(self, name: str, json_args: str) -> str:
        if name not in self._tools:
            return json.dumps({"ok": False, "error": f"unknown tool {name}"})
        return self._tools[name].run(json_args)

    def names(self) -> List[str]:
        return list(self._tools.keys())

    def schemas(self) -> List[dict]:
        return [t.schema() for t in self._tools.values()]
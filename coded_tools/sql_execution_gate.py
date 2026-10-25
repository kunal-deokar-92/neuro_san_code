
"""Demo-only SQL execution gate.

This tool evaluates supplied policy results but never executes SQL.
A future live executor must enforce authorization independently.
"""
import json
from typing import Any
from neuro_san.interfaces.coded_tool import CodedTool


class SqlExecutionGate(CodedTool):
    async def async_invoke(
        self, args: dict[str, Any], sly_data: dict[str, Any]
    ) -> str:
        sql = str(args.get("sql", "")).strip()
        approval_confirmed = args.get("approval_confirmed", False)
        validation_result = args.get("validation_result", {})

        if isinstance(validation_result, str):
            try:
                validation_result = json.loads(validation_result)
            except (json.JSONDecodeError, TypeError):
                validation_result = {}

        if not isinstance(validation_result, dict):
            validation_result = {}

        findings = []

        if not sql:
            findings.append("No SQL statement was supplied.")

        if validation_result.get("valid") is not True:
            findings.append(
                "A successful validator result was not supplied."
            )

        if validation_result.get("approval_required") is True:
            if approval_confirmed is not True:
                findings.append(
                    "Explicit approval has not been confirmed."
                )

        # This prototype intentionally has no database execution capability.
        return json.dumps({
            "status": "BLOCKED_DEMO_MODE",
            "execution_performed": False,
            "execution_allowed": False,
            "approval_confirmed": approval_confirmed is True,
            "findings": findings,
            "message": (
                "Demo execution gate only. No database connection exists "
                "and SQL was not executed. Approval status supplied to "
                "this tool is not independently authenticated."
            ),
        })

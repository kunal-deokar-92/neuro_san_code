"""Restricted Snowflake SQL policy validator for Neuro SAN.
This is a pre-check, not a full SQL parser. It never connects to or executes SQL.
"""
import json
import re
from typing import Any, List, Tuple
from neuro_san.interfaces.coded_tool import CodedTool

ALLOWED_OPERATIONS = {
    "SELECT", "CREATE TABLE", "CREATE VIEW", "ALTER TABLE",
    "DROP TABLE", "DROP VIEW", "TRUNCATE TABLE",
    "INSERT", "UPDATE", "DELETE", "MERGE", "GRANT", "REVOKE",
}
APPROVAL_REQUIRED_OPERATIONS = {
    "DROP TABLE", "DROP VIEW", "TRUNCATE TABLE", "DELETE",
    "UPDATE", "GRANT", "REVOKE", "ALTER TABLE",
}
MAX_SQL_LENGTH = 100_000


def split_sql_statements(sql: str) -> Tuple[List[str], List[str]]:
    """Split only on semicolons outside quoted strings and comments."""
    statements: List[str] = []
    errors: List[str] = []
    current: List[str] = []
    i, n, state, dollar_tag = 0, len(sql), "normal", ""

    def finish() -> None:
        statement = "".join(current).strip()
        if statement:
            statements.append(statement)
        current.clear()

    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        if state == "single":
            current.append(ch)
            if ch == "'" and nxt == "'":
                current.append(nxt); i += 2; continue
            if ch == "'": state = "normal"
            i += 1; continue
        if state == "double":
            current.append(ch)
            if ch == '"' and nxt == '"':
                current.append(nxt); i += 2; continue
            if ch == '"': state = "normal"
            i += 1; continue
        if state == "dollar":
            if sql.startswith(dollar_tag, i):
                current.append(dollar_tag); i += len(dollar_tag)
                state = "normal"; continue
            current.append(ch); i += 1; continue
        if state == "line_comment":
            if ch == "\n":
                current.append(" "); state = "normal"
            i += 1; continue
        if state == "block_comment":
            if ch == "*" and nxt == "/":
                current.append(" "); i += 2; state = "normal"; continue
            i += 1; continue

        if ch == "'":
            current.append(ch); state = "single"; i += 1; continue
        if ch == '"':
            current.append(ch); state = "double"; i += 1; continue
        if ch == "-" and nxt == "-":
            current.append(" "); state = "line_comment"; i += 2; continue
        if ch == "/" and nxt == "*":
            current.append(" "); state = "block_comment"; i += 2; continue
        if ch == "$":
            match = re.match(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$", sql[i:])
            if match:
                dollar_tag = match.group(0); current.append(dollar_tag)
                state = "dollar"; i += len(dollar_tag); continue
        if ch == ";":
            finish(); i += 1; continue
        current.append(ch); i += 1

    if state in {"single", "double", "dollar"}:
        errors.append("Unterminated quoted string or identifier detected.")
    elif state == "block_comment":
        errors.append("Unterminated block comment detected.")
    finish()
    return statements, errors


def normalize_operation(statement: str) -> str:
    match = re.match(
        r"(?is)^\s*(SELECT|INSERT|UPDATE|DELETE|MERGE|GRANT|REVOKE)\b",
        statement,
    )
    if match:
        return match.group(1).upper()
    match = re.match(
        r"(?is)^\s*(CREATE|ALTER|DROP|TRUNCATE)\s+"
        r"(?:OR\s+REPLACE\s+)?(?:TEMPORARY\s+|TEMP\s+|TRANSIENT\s+)?"
        r"(TABLE|VIEW)\b",
        statement,
    )
    if match:
        return f"{match.group(1).upper()} {match.group(2).upper()}"
    match = re.match(r"(?is)^\s*([A-Za-z]+)\b", statement)
    return match.group(1).upper() if match else "UNKNOWN"


def object_name_findings(statement: str, operation: str) -> List[str]:
    if operation not in {
        "CREATE TABLE", "CREATE VIEW", "ALTER TABLE",
        "DROP TABLE", "DROP VIEW", "TRUNCATE TABLE",
    }:
        return []
    pattern = (
        r"(?is)^\s*(?:CREATE|ALTER|DROP|TRUNCATE)\s+"
        r"(?:OR\s+REPLACE\s+)?(?:TEMPORARY\s+|TEMP\s+|TRANSIENT\s+)?"
        r"(?:TABLE|VIEW)\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?"
        r"([A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*){0,2})\b"
    )
    if not re.match(pattern, statement):
        return ["Could not confidently validate the object name for this DDL statement."]
    return []


class SqlValidator(CodedTool):
    """Policy-check SQL without database access or execution."""

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        sql = args.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            return json.dumps({
                "valid": False, "operation": "UNKNOWN",
                "approval_required": False, "execution_allowed": False,
                "findings": ["A non-empty SQL string is required."],
                "note": "No database connection or SQL execution is performed.",
            })
        if len(sql) > MAX_SQL_LENGTH:
            return json.dumps({
                "valid": False, "operation": "UNKNOWN",
                "approval_required": False, "execution_allowed": False,
                "findings": [f"SQL input exceeds the {MAX_SQL_LENGTH}-character policy limit."],
                "note": "Input rejected before further parsing. No SQL was executed.",
            })

        statements, lexical_errors = split_sql_statements(sql)
        findings = list(lexical_errors)
        if not statements:
            findings.append("No SQL statement was detected.")
            return json.dumps({
                "valid": False, "operation": "UNKNOWN", "statement_count": 0,
                "approval_required": False, "execution_allowed": False,
                "findings": findings,
                "note": "Initial policy check only; no database connection or SQL execution.",
            })

        operations = [normalize_operation(s) for s in statements]
        approval_required = any(op in APPROVAL_REQUIRED_OPERATIONS for op in operations)

        # Critical fix: reject the whole input before considering any one
        # statement valid. This prevents a CREATE + DROP batch from passing.
        if len(statements) > 1:
            findings.insert(
                0, f"Multiple SQL statements detected ({len(statements)}). "
                "Submit and validate one statement per request."
            )
            for op in operations:
                if op not in ALLOWED_OPERATIONS:
                    findings.append(
                        f"Operation '{op}' is not in the validator's allowed-operation list."
                    )
            if approval_required:
                findings.append(
                    "At least one statement is destructive or privilege-changing "
                    "and requires explicit approval through a trusted approval workflow."
                )
            return json.dumps({
                "valid": False, "operation": "MULTIPLE",
                "operations": operations, "statement_count": len(statements),
                "approval_required": approval_required, "execution_allowed": False,
                "findings": findings,
                "note": "The complete request was rejected because it contains multiple "
                        "statements. No database connection or SQL execution is performed.",
            }, indent=2)

        operation = operations[0]
        if lexical_errors:
            findings.append("Malformed or unsupported quoting/comment syntax; rejected fail-closed.")
        if operation not in ALLOWED_OPERATIONS:
            findings.append(
                f"Operation '{operation}' is not in the validator's allowed-operation list."
            )
        findings.extend(object_name_findings(statements[0], operation))

        if operation in {"UPDATE", "DELETE"} and not re.search(r"(?is)\bWHERE\b", statements[0]):
            findings.append(f"{operation} statement has no WHERE clause; explicit review is required.")
            approval_required = True

        # Findings that already exist at this point are blocking policy or
        # lexical problems. Approval warnings alone do not make SQL invalid.
        blocking_findings = list(findings)
        if operation in APPROVAL_REQUIRED_OPERATIONS:
            findings.append(
                f"{operation} is classified as destructive or privilege-changing "
                "and requires explicit approval through a trusted approval workflow."
            )
            approval_required = True

        valid = not blocking_findings and operation in ALLOWED_OPERATIONS
        if valid and not approval_required:
            findings.append("Initial policy checks passed.")
        return json.dumps({
            "valid": valid, "operation": operation, "statement_count": 1,
            "approval_required": approval_required,
            "execution_allowed": False,
            "findings": findings,
            "note": "This is an initial policy check, not a complete Snowflake SQL parser. "
                    "No database connection or SQL execution is performed.",
        }, indent=2)

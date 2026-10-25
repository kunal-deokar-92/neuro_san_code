# Neuro SAN Snowflake Database Development Assistant

## 1. Overview

The **Snowflake Database Development Assistant** is a multi-agent prototype built with Neuro SAN. It assists with database-development tasks by coordinating SQL generation, policy checks, independent SQL review, sample metadata inspection, and an execution-control decision.

The current project is a **demo-mode prototype**. It does not connect to a live Snowflake account and does not execute SQL. Metadata returned by the metadata tool is illustrative sample data.

## 2. Goals

- Generate Snowflake SQL from natural-language requests.
- Apply initial policy checks to generated SQL.
- Have a separate reviewer assess SQL for apparent correctness, security, and best practices.
- Demonstrate integration of a metadata-inspection tool.
- Keep SQL execution separate from generation and review; the current execution gate blocks execution.

## 3. Architecture

```text
User request
    |
    v
Coordinator
    |
    +---- SQL Generator (/generated/snow_database_sql_generator)
    |          |
    |          v
    |      Generated SQL
    |          |
    |          +----> SQL_Validator
    |          |
    |          +----> SQL_Reviewer
    |
    +---- Snowflake_Metadata (metadata requests)
    |          |
    |          v
    |      Sample metadata (DEMO_ONLY)
    |
    +---- SQL_Execution_Gate (execution-decision requests)
               |
               v
          BLOCKED_DEMO_MODE
          No SQL execution
```

The exact tool-call sequence depends on the Coordinator instructions and user request. Metadata lookup is a separate branch and is not necessarily required for every SQL request.

## 4. Repository layout

```text
neuro-san/
├── coded_tools/
│   ├── sql_validator.py
│   ├── snowflake_metadata.py
│   └── sql_execution_gate.py
└── registries/
    ├── manifest.hocon
    └── generated/
        ├── manifest.hocon
        └── snowflake_database_development_assistant.hocon
```

Other files may exist. The network HOCON file contains the Coordinator and tool definitions. Registry manifests make configured networks discoverable by Neuro SAN.

## 5. Components

### Coordinator

The entry point for requests. Its configured instructions route SQL requests to `/generated/snow_database_sql_generator`, pass generated SQL to `SQL_Validator`, include validator findings in the review request, and return the SQL and review findings. It should never claim execution occurred.

### SQL Generator

The existing `/generated/snow_database_sql_generator` network creates proposed Snowflake SQL from natural-language requirements. Its output is a proposal, not database-tested SQL.

### SQL_Validator

`coded_tools/sql_validator.py` performs restricted policy checks: it identifies supported operations, checks selected naming/policy rules, flags selected risky operations, and reports approval requirements.

Limitations:
- It is a heuristic pre-check, not a complete Snowflake SQL parser.
- It does not connect to Snowflake or execute SQL.
- `valid: true` means only that the implemented checks passed; it does not prove the SQL compiles or behaves correctly in Snowflake.
- Multi-statement handling should be verified directly before relying on it as a security boundary.
- Its rules may not catch every destructive or privilege-changing statement.

### SQL_Reviewer

The reviewer independently assesses SQL for apparent syntax issues, requirement coverage, naming, performance, security, destructive operations, and privilege concerns. It may return PASS/FAIL, severity, findings, and suggested corrections.

A reviewer PASS is advisory. It is not execution approval and does not prove that SQL was tested against a live database.

### Snowflake_Metadata

`coded_tools/snowflake_metadata.py` returns fixed example metadata, including sample tables such as `CUSTOMER_DETAILS` and `CUSTOMER_TRANSACTIONS`.

Its output includes:
- `status: DEMO_ONLY`
- `sample_data: true`
- `live_database_connected: false`

It does **not** query Snowflake. The returned metadata is illustrative and must not be presented as live environment information.

### SQL_Execution_Gate

`coded_tools/sql_execution_gate.py` demonstrates the separation between SQL generation/review and execution. It accepts SQL, a serialized validator result, and an `approval_confirmed` flag, then returns a gate result.

In this version:
- The gate always returns `status: BLOCKED_DEMO_MODE`.
- `execution_performed` and `execution_allowed` are always `false`.
- No database connection is created and no SQL is executed.
- The supplied approval flag is not authenticated; it is only a demo input, not proof of approval.

This is not a production execution mechanism.

## 6. Setup and run

Assuming the project and Python virtual environment are already installed:

1. Open PowerShell in the project root.
2. Activate the existing virtual environment if needed.
3. Compile the coded tools:

   ```powershell
   python -m py_compile .\coded_tools\sql_validator.py .\coded_tools\snowflake_metadata.py .\coded_tools\sql_execution_gate.py
   ```

4. Start Neuro SAN from the repository root:

   ```powershell
   ns run
   ```

5. Open the Neuro SAN Studio URL configured by your setup (commonly `http://localhost:4173/`) and select `snowflake_database_development_assistant`.

If a registry parsing error occurs, check commas, braces, and ensure tool definitions are inside the outer `tools` array. Confirm the network is registered in the appropriate manifest.

## 7. Demo scenarios

### Scenario A — inspect sample metadata

Prompt:

> Use `Snowflake_Metadata` to inspect `BANKING_DB.CUSTOMERS`. Return the tables and columns from the tool output. Clearly state whether the information came from a live database.

Expected: sample tables and columns with `DEMO_ONLY`, `sample_data: true`, and `live_database_connected: false`.

### Scenario B — generate, validate, and review SQL

Prompt:

> Generate a Snowflake `CREATE TABLE` statement for `CUSTOMER_RISK_SUMMARY` with `CUSTOMER_ID NUMBER(18,0)`, `TOTAL_SPEND NUMBER(12,2)`, and `RISK_LEVEL VARCHAR(50)`. Validate it and have the reviewer independently assess it. Do not execute it.

Expected: proposed SQL, validator findings, and reviewer verdict/recommendations. These are not live database test results.

### Scenario C — demonstrate the execution gate

Prompt:

> Check `DROP TABLE CUSTOMER_DETAILS` with `SQL_Validator`, then call `SQL_Execution_Gate` with the validator result and `approval_confirmed: false`. Return the raw gate result. Do not execute SQL.

Expected result includes:

```json
{
  "status": "BLOCKED_DEMO_MODE",
  "execution_performed": false,
  "execution_allowed": false,
  "approval_confirmed": false
}
```

The gate does not execute the statement.

## 8. Current limitations

- No live Snowflake account is configured.
- Metadata is fixed demo data, not queried from a database.
- SQL is not executed.
- Validation is a restricted heuristic, not a full parser or database compilation test.
- Reviewer output is advisory and can be incorrect; generated SQL must be independently checked.
- The execution gate accepts an unverified boolean and is not an authenticated approval workflow.
- A successful policy check or reviewer PASS does not authorize execution.
- Multi-statement rejection behavior should be verified directly before treating it as a reliable control.

## 9. Next development phase

1. Connect to a dedicated Snowflake development account using secrets stored outside source control.
2. Use a least-privilege Snowflake role.
3. Query live metadata through `INFORMATION_SCHEMA` or supported metadata commands.
4. Use a proper SQL parser or stricter allowlisted grammar for policy checks.
5. Implement authenticated approvals tied to the exact SQL text/hash, requester, approver, environment, and expiration.
6. Enforce policy and authorization in trusted server-side code, not in LLM instructions alone.
7. Execute only approved statements through a restricted database tool with audit logging, timeouts, and explicit allowlists.
8. Add automated tests for allowed and blocked operations, multiple statements, comments, quoted strings, and privilege-changing SQL.
9. Add integration tests against a non-production Snowflake environment before deployment.

## 10. Summary

The project demonstrates a multi-agent pattern for assisted database development: SQL generation, policy checking, independent review, a metadata-tool interface, and a separate execution-control gate. The current release is a demo prototype. Live Snowflake connectivity and actual execution are future work; the system should not be represented as production-ready.

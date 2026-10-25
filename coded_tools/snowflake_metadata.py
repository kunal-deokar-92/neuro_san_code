
"""Demo metadata inspector for the Neuro SAN Snowflake assistant.

Returns explicitly labeled sample metadata. It does not connect to Snowflake.
"""
import json
from typing import Any
from neuro_san.interfaces.coded_tool import CodedTool


class SnowflakeMetadata(CodedTool):
    async def async_invoke(
        self, args: dict[str, Any], sly_data: dict[str, Any]
    ) -> str:
        database = str(args.get("database", "BANKING_DB")).strip().upper()
        schema = str(args.get("schema", "CUSTOMERS")).strip().upper()

        # Fixed demonstration data only. Never represent this as live metadata.
        sample_tables = [
            {
                "name": "CUSTOMER_DETAILS",
                "columns": [
                    {"name": "CUSTOMER_ID", "type": "NUMBER"},
                    {"name": "CUSTOMER_NAME", "type": "VARCHAR"},
                    {"name": "EMAIL", "type": "VARCHAR"},
                ],
            },
            {
                "name": "CUSTOMER_TRANSACTIONS",
                "columns": [
                    {"name": "TRANSACTION_ID", "type": "NUMBER"},
                    {"name": "CUSTOMER_ID", "type": "NUMBER"},
                    {"name": "AMOUNT", "type": "NUMBER(12,2)"},
                    {"name": "TRANSACTION_DATE", "type": "TIMESTAMP_NTZ"},
                ],
            },
        ]

        return json.dumps({
            "status": "DEMO_ONLY",
            "database": database,
            "schema": schema,
            "tables": sample_tables,
            "sample_data": True,
            "live_database_connected": False,
            "message": (
                "Illustrative metadata only. No Snowflake connection "
                "was made and no live metadata was retrieved."
            ),
        })

import csv
import time
from pathlib import Path
from app.tools.failure_switch import is_tool_unavailable

from app.state import ToolResult, ToolStatus

DATA = Path(__file__).resolve().parents[2] / "data" / "customers.csv"


def fetch_customer_profile(customer_id: str) -> ToolResult:

    started = time.perf_counter()

    try:
        # Simulate an unavailable service for failure testing
        if is_tool_unavailable("customer_profile"):
                return ToolResult(
                tool_name="customer_profile",
                status=ToolStatus.UNAVAILABLE,
                source_ids=[],
                data={},
                error_message="Simulated customer profile service timeout",
                execution_time_ms=(time.perf_counter() - started) * 1000
            )

        with DATA.open(
            newline="",
            encoding="utf-8"
        ) as file:
            customers = list(csv.DictReader(file))

        customer = next(
            (
                row for row in customers
                if row["customer_id"] == customer_id
            ),
            None
        )

        if customer is None:
            return ToolResult(
                tool_name="customer_profile",
                status=ToolStatus.ERROR,
                source_ids=[],
                data={},
                error_message=f"Customer not found: {customer_id}",
                execution_time_ms=(time.perf_counter() - started) * 1000
            )

        # Convert numeric fields
        for field in [
            "monthly_income",
            "annual_income",
            "expected_monthly_volume"
        ]:
            customer[field] = float(customer[field])

        # Stable source IDs for claim verification
        customer_key = customer_id.replace("CUST-", "")

        source_ids = [
        f"CUST_{customer_key}_KYC",
        f"CUST_{customer_key}_OCCUPATION",
        f"CUST_{customer_key}_RISK"
        ]

        return ToolResult(
            tool_name="customer_profile",
            status=ToolStatus.SUCCESS,
            source_ids=source_ids,
            data=customer,
            execution_time_ms=(time.perf_counter() - started) * 1000
        )

    except Exception as exc:
        return ToolResult(
            tool_name="customer_profile",
            status=ToolStatus.ERROR,
            source_ids=[],
            data={},
            error_message=str(exc),
            execution_time_ms=(time.perf_counter() - started) * 1000
        )


"""Synthetic transaction history lookup tool."""

import csv
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from app.tools.failure_switch import is_tool_unavailable

from app.state import ToolResult, ToolStatus

DATA = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "transactions.csv"
)


def fetch_transactions(
    customer_id: str,
    lookback_days: int = 90
) -> ToolResult:

    started = time.perf_counter()

    try:
        if is_tool_unavailable("transactions"):
            return ToolResult(
                tool_name="transactions",
                status=ToolStatus.UNAVAILABLE,
                source_ids=[],
                data={},
                error_message="Simulated core banking timeout",
                execution_time_ms=(
                    time.perf_counter() - started
                ) * 1000
            )

        if lookback_days < 1:
            raise ValueError("lookback_days must be >= 1")

        with DATA.open(
            newline="",
            encoding="utf-8"
        ) as file:
            rows = [
                row for row in csv.DictReader(file)
                if row["customer_id"] == customer_id
            ]

        cutoff = date.today() - timedelta(days=lookback_days)

        parsed = [
            (
                row,
                datetime.strptime(
                    row["date"], "%Y-%m-%d"
                ).date()
            )
            for row in rows
        ]

        recent = [
            row for row, tx_date in parsed
            if tx_date >= cutoff
        ]

        # Retain fixed synthetic demo records if the
        # dataset dates fall outside the requested window.
        if rows and not recent:
            recent = rows

        for row in recent:
            row["amount"] = float(row["amount"])

        source_ids = [
        "TX_" + row["transaction_id"].replace("TX-", "")
        for row in recent
        ]

        total_volume = round(
            sum(row["amount"] for row in recent), 2
        )

        return ToolResult(
            tool_name="transactions",
            status=ToolStatus.SUCCESS,
            source_ids=source_ids,
            data={
                "customer_id": customer_id,
                "lookback_days": lookback_days,
                "transaction_count": len(recent),
                "total_volume": total_volume,
                "records": recent
            },
            execution_time_ms=(
                time.perf_counter() - started
            ) * 1000
        )

    except Exception as exc:
        return ToolResult(
            tool_name="transactions",
            status=ToolStatus.ERROR,
            source_ids=[],
            data={},
            error_message=str(exc),
            execution_time_ms=(
                time.perf_counter() - started
            ) * 1000
        )

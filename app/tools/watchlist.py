
"""Synthetic watchlist screening with fuzzy name matching."""

import csv
import time
from difflib import SequenceMatcher
from pathlib import Path
from app.tools.failure_switch import is_tool_unavailable

from app.state import ToolResult, ToolStatus

DATA = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "watchlist.csv"
)


def normalize_name(name: str) -> str:
    """Normalize names before comparison."""
    return " ".join(
        "".join(
            ch.lower() if ch.isalnum() else " "
            for ch in (name or "")
        ).split()
    )


def screen_watchlist(
    customer_name: str,
    dob: str = None,
    country: str = None
) -> ToolResult:

    started = time.perf_counter()

    try:
        if is_tool_unavailable("watchlist"):
            return ToolResult(
                tool_name="watchlist",
                status=ToolStatus.UNAVAILABLE,
                source_ids=[],
                data={},
                error_message="Simulated screening provider timeout",
                execution_time_ms=(
                    time.perf_counter() - started
                ) * 1000
            )

        query = normalize_name(customer_name)

        if not query:
            raise ValueError("customer_name is required")

        with DATA.open(
            newline="",
            encoding="utf-8"
        ) as file:
            entries = list(csv.DictReader(file))

        matches = []

        for entry in entries:

            score = round(
                100 * SequenceMatcher(
                    None,
                    query,
                    normalize_name(entry["name"])
                ).ratio(),
                1
            )

            dob_match = bool(
                dob and dob == entry.get("dob")
            )

            country_match = bool(
                country and
                country.upper() ==
                entry.get("nationality", "").upper()
            )

            adjusted_score = min(
                100.0,
                score
                + (5 if dob_match else 0)
                + (3 if country_match else 0)
            )

            if score >= 55 or dob_match or country_match:

                matches.append({
                    **entry,
                    "name_similarity_score": score,
                    "dob_match": dob_match,
                    "country_match": country_match,
                    "match_score": adjusted_score
                })

        matches.sort(
            key=lambda item: item["match_score"],
            reverse=True
        )

        top = matches[0] if matches else None

        if top and top["match_score"] >= 85:
            source_id = (
                "WL_HIT_" +
                top["entity_id"].replace("-", "_")
            )
        else:
            source_id = (
                "WL_CLEAN_" +
                customer_name.strip().upper().replace(" ", "_")
            )

        return ToolResult(
            tool_name="watchlist",
            status=ToolStatus.SUCCESS,
            source_ids=[source_id],
            data={
                "query_name": customer_name,
                "match_found": bool(
                    top and top["match_score"] >= 85
                ),
                "highest_similarity_score": (
                    top["match_score"] if top else 0.0
                ),
                "matched_entries": matches[:5]
            },
            execution_time_ms=(
                time.perf_counter() - started
            ) * 1000
        )

    except Exception as exc:

        return ToolResult(
            tool_name="watchlist",
            status=ToolStatus.ERROR,
            source_ids=[],
            data={},
            error_message=str(exc),
            execution_time_ms=(
                time.perf_counter() - started
            ) * 1000
        )

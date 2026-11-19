
"""FastAPI service for AML Alert Investigator.
Exposes investigation, approval, state retrieval and health endpoints.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from fastapi.encoders import jsonable_encoder

from app.graph import run_investigation, resume_investigation, aml_graph


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="AML Alert Investigator API",
    description="Agentic AI Banking Operations and AML Investigation Assistant",
    version="1.0.0",
)

# Enable CORS for browser frontends (e.g. React/Vite on localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class ApprovalRequest(BaseModel):
    approved: bool

    reviewer_id: str = "compliance_analyst"

    edited_note: Optional[str] = None

    reviewer_comments: Optional[str] = None

    disposition_override: Optional[str] = None


# ============================================================
# HELPER FUNCTION
# ============================================================

def get_thread_state(thread_id: str) -> Dict[str, Any]:
    """Retrieve the latest saved state for an investigation."""

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    snapshot = aml_graph.get_state(config)

    if not snapshot or not snapshot.values:
        raise HTTPException(
            status_code=404,
            detail=f"No investigation found for ID: {thread_id}"
        )

    return snapshot.values


# ============================================================
# 0. FRONTEND WEB APPLICATION
# ============================================================

@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
def serve_web_frontend():
    """Serves the standalone modern React/Tailwind compliance dashboard."""
    index_file = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h2>AML Alert Investigator API Live</h2><p>Visit <a href='/docs'>/docs</a></p>")


# ============================================================
# 1. HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AML Alert Investigator API",
        "version": "1.0.0"
    }


# ============================================================
# 2. START INVESTIGATION
# ============================================================

@app.post("/alerts/investigate")
def investigate_alert(payload: Dict[str, Any]):

    alert_id = payload.get("alert_id")

    if not alert_id or not isinstance(alert_id, str):
        raise HTTPException(
            status_code=400,
            detail="A valid alert_id is required."
        )

    try:
        result = run_investigation(
            alert_payload=payload,
            thread_id=alert_id
        )

        return jsonable_encoder({
            "message": "Investigation execution completed or paused for review.",
            "alert_id": alert_id,
            "state": result
        })

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Investigation failed due to an internal processing error."
        )


# ============================================================
# 3. APPROVE OR REJECT INVESTIGATION
# ============================================================

@app.post("/alerts/{alert_id}/approve")
def approve_alert(
    alert_id: str,
    request: ApprovalRequest
):

    try:
        # Verify that the investigation exists.
        get_thread_state(alert_id)

        result = resume_investigation(
            thread_id=alert_id,
            approved=request.approved,
            reviewer_id=request.reviewer_id,
            edited_note=request.edited_note,
            reviewer_comments=request.reviewer_comments,
            disposition_override=request.disposition_override
        )

        return jsonable_encoder({
            "message": (
                "Investigation approved and finalized."
                if request.approved
                else "Investigation rejected and routed for escalation."
            ),
            "alert_id": alert_id,
            "state": result
        })

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to process the analyst decision."
        )


# ============================================================
# 4. GET INVESTIGATION STATE
# ============================================================

@app.get("/alerts/{alert_id}/state")
def get_alert_state(alert_id: str):

    state = get_thread_state(alert_id)

    return jsonable_encoder({
        "alert_id": alert_id,
        "state": state
    })


# ============================================================
# 5. LIST AVAILABLE ALERTS (FOR FRONTEND QUEUE)
# ============================================================

@app.get("/alerts")
def list_alerts():
    """Retrieve all pre-configured synthetic banking alerts from dataset."""
    alerts_path = Path(__file__).resolve().parent.parent / "data" / "alerts.json"
    if alerts_path.exists():
        with open(alerts_path, "r", encoding="utf-8") as f:
            alerts = json.load(f)
            return jsonable_encoder({"alerts": alerts, "total": len(alerts)})
    return jsonable_encoder({"alerts": [], "total": 0})


# ============================================================
# 6. EVALUATION BENCHMARK SUMMARY
# ============================================================

@app.get("/eval/summary")
def get_eval_summary():
    """Retrieve the latest markdown evaluation benchmark report."""
    report_path = Path(__file__).resolve().parent.parent / "eval" / "reports" / "eval_summary.md"
    if report_path.exists():
        return {"report_markdown": report_path.read_text(encoding="utf-8")}
    return {"report_markdown": None}

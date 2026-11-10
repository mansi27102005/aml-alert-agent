
"""FastAPI service for AML Alert Investigator.
Exposes investigation, approval, state retrieval and health endpoints.
"""

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
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

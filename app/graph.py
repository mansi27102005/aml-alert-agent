"""LangGraph State Machine for AML Alert Investigator (Role A).
Constructs the compiled graph connecting nodes, cyclic redraft loops,
adversarial verifier checks, human interrupts, and circuit breaker escalations.
"""

from typing import Any, Dict, Literal, Optional
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.nodes import (
    apply_human_decision,
    claim_check_node,
    classify_node,
    draft_note_node,
    escalate_node,
    finalize_node,
    gather_evidence_node,
    human_approval_node,
    intake_node,
    retrieve_policy_node,
    risk_router_node,
    verifier_node,
)
from app.state import AlertState, InvestigationStatus, create_initial_state

# ============================================================================
# CONDITIONAL ROUTING FUNCTIONS (DETERMINISTIC CODE)
# ============================================================================

def route_after_intake(state: AlertState) -> Literal["classify", "escalate"]:
    """Routes to classification or aborts to escalation if intake validation failed."""
    if state.get("status") == InvestigationStatus.ESCALATED.value:
        return "escalate"
    return "classify"


def route_after_claim_check(state: AlertState) -> Literal["verifier", "draft_note", "escalate"]:
    """Evaluates the claim ledger result:
    - If valid citations -> proceed to verifier
    - If invalid and redraft_count <= MAX_REDRAFTS -> retry draft_note with error hints
    - If still failing -> trigger circuit breaker to escalate
    """
    if state.get("claim_check_passed", False):
        return "verifier"

    # Redraft budget check
    if state.get("redraft_count", 0) <= settings.MAX_REDRAFTS:
        return "draft_note"

    return "escalate"


def route_after_verifier(state: AlertState) -> Literal["risk_router", "escalate"]:
    """Evaluates 2nd-Line QA skeptic verdict:
    - If verifier agrees with reasoning -> proceed to risk router
    - If verifier finds compliance flaws/omissions -> escalate to senior officer
    """
    if state.get("verifier_agreed", False):
        return "risk_router"
    return "escalate"


# ============================================================================
# GRAPH BUILDER
# ============================================================================

def build_aml_graph(checkpointer: Optional[Any] = None, enable_interrupt: bool = True):
    """Builds and compiles the complete AML LangGraph State Machine.
    Args:
        checkpointer: Checkpoint saver (e.g. MemorySaver) for thread persistence.
        enable_interrupt: If True, interrupts before human_approval for HITL review.
    """
    workflow = StateGraph(AlertState)

    # 1. Register Nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("classify", classify_node)
    workflow.add_node("retrieve_policy", retrieve_policy_node)
    workflow.add_node("gather_evidence", gather_evidence_node)
    workflow.add_node("draft_note", draft_note_node)
    workflow.add_node("claim_check", claim_check_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("risk_router", risk_router_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("escalate", escalate_node)
    workflow.add_node("finalize", finalize_node)

    # 2. Sequential Edges
    workflow.add_edge(START, "intake")
    workflow.add_conditional_edges("intake", route_after_intake)
    workflow.add_edge("classify", "retrieve_policy")
    workflow.add_edge("retrieve_policy", "gather_evidence")
    workflow.add_edge("gather_evidence", "draft_note")
    workflow.add_edge("draft_note", "claim_check")

    # 3. Cyclic / Conditional Edges
    workflow.add_conditional_edges("claim_check", route_after_claim_check)
    workflow.add_conditional_edges("verifier", route_after_verifier)

    # 4. Review & Finalization Paths
    workflow.add_edge("risk_router", "human_approval")
    workflow.add_edge("human_approval", "finalize")
    workflow.add_edge("escalate", "finalize")
    workflow.add_edge("finalize", END)

    # 5. Compilation with Persistence

    memory = checkpointer if checkpointer is not None else MemorySaver()

    interrupts = ["human_approval"] if enable_interrupt else []

    app = workflow.compile(
       checkpointer=memory,
       interrupt_after=interrupts,
   )
    return app



# Singleton compiled graph instance
graph_memory = MemorySaver()
aml_graph = build_aml_graph(checkpointer=graph_memory, enable_interrupt=True)


# ============================================================================
# CONVENIENCE EXECUTION RUNNERS
# ============================================================================

def run_investigation(alert_payload: Dict[str, Any], thread_id: Optional[str] = None) -> AlertState:
    """Runs an alert investigation up to the human interrupt point (or escalation)."""
    initial_state = create_initial_state(alert_payload)
    tid = thread_id or initial_state["alert_id"]
    config = {"configurable": {"thread_id": tid}}

    # Executes until interrupt_before=['human_approval'] or END
    result = aml_graph.invoke(initial_state, config=config)
    return result


def resume_investigation(
    thread_id: str,
    approved: bool,
    reviewer_id: str = "compliance_analyst",
    edited_note: Optional[str] = None,
    reviewer_comments: Optional[str] = None,
    disposition_override: Optional[str] = None,
) -> AlertState:
    """Resumes an interrupted LangGraph thread with analyst review decision."""
    config = {"configurable": {"thread_id": thread_id}}

    # Retrieve existing state from checkpoint
    current_snapshot = aml_graph.get_state(config)
    if not current_snapshot or not current_snapshot.values:
        raise ValueError(f"No active investigation found for thread_id '{thread_id}'.")

    # Inject human decision updates
    current_values = current_snapshot.values
    decision_updates = apply_human_decision(
        current_values,
        approved=approved,
        reviewer_id=reviewer_id,
        edited_note=edited_note,
        reviewer_comments=reviewer_comments,
        disposition_override=disposition_override,
    )

    aml_graph.update_state(config, decision_updates)

    # Resume graph execution until finalize and END
    resumed_result = aml_graph.invoke(None, config=config)
    return resumed_result

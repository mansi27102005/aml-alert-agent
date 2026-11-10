
"""Streamlit dashboard for AML Alert Investigator.
Connects to the Role A FastAPI backend.
"""

import os
import json
import requests
import streamlit as st


# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------

API_BASE_URL = os.getenv(
    "AML_API_URL",
    "http://127.0.0.1:8000"
).rstrip("/")

st.set_page_config(
    page_title="AML Alert Investigator",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ------------------------------------------------------------
# API HELPERS
# ------------------------------------------------------------

def api_get(endpoint):
    try:
        response = requests.get(
            f"{API_BASE_URL}{endpoint}",
            timeout=30
        )
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as exc:
        return None, str(exc)


def api_post(endpoint, payload):
    try:
        response = requests.post(
            f"{API_BASE_URL}{endpoint}",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.HTTPError:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        return None, str(detail)
    except requests.exceptions.RequestException as exc:
        return None, str(exc)


def show_api_error(message):
    st.error(f"API request failed: {message}")


def get_state_value(state, key, default="Not available"):
    value = state.get(key, default)
    if value is None or value == "":
        return default
    return value


def show_evidence(state):
    evidence = state.get("evidence", {})

    if not evidence:
        st.info("No evidence is available in this case yet.")
        return

    for tool_name, tool_result in evidence.items():
        if not isinstance(tool_result, dict):
            continue

        status = tool_result.get("status", "UNKNOWN")
        source_ids = tool_result.get("source_ids", [])

        with st.expander(
            f"{tool_name.replace('_', ' ').title()} — {status}",
            expanded=False
        ):
            st.write("**Source IDs:**")
            if source_ids:
                st.write(", ".join(map(str, source_ids)))
            else:
                st.write("No source IDs returned.")

            st.write("**Evidence data:**")
            st.json(tool_result.get("data", {}))


def show_case_summary(state):
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Alert ID",
            get_state_value(state, "alert_id", "N/A")
        )

    with col2:
        st.metric(
            "Alert Type",
            get_state_value(state, "alert_type", "N/A")
        )

    with col3:
        st.metric(
            "Risk Tier",
            get_state_value(state, "risk_tier", "N/A")
        )

    with col4:
        st.metric(
            "Status",
            get_state_value(state, "status", "N/A")
        )


def show_investigation_details(state,view_id="default"):
    show_case_summary(state)

    st.subheader("Investigation Quality Checks")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Claim Check",
            "Passed" if state.get("claim_check_passed") else "Not passed"
        )

    with col2:
        st.metric(
            "Verifier",
            "Agreed" if state.get("verifier_agreed") else "Not agreed"
        )

    with col3:
        st.metric(
            "Redraft Count",
            state.get("redraft_count", 0)
        )

    st.subheader("Draft Investigation Narrative")

    draft = (
        state.get("human_edits")
        or state.get("draft_note")
        or "No draft narrative generated."
    )

    st.text_area(
    "Investigation narrative",
    value=str(draft),
    height=280,
    disabled=True,
    key=f"display_draft_{view_id}_{state.get('alert_id', 'unknown')}"
)

    st.subheader("Retrieved Policies")

    policy_chunks = state.get("policy_chunks", [])

    if policy_chunks:
        for policy in policy_chunks:
            with st.expander(
                policy.get("title", policy.get("source_id", "Policy"))
            ):
                st.write(policy.get("content", ""))
                st.caption(
                    f"Source: {policy.get('source_id', 'Unknown')}"
                )
    else:
        st.info("No policy chunks returned.")

    st.subheader("Evidence Retrieved")
    show_evidence(state)

    st.subheader("Audit Trail")

    audit_log = state.get("audit_log", [])

    if audit_log:
        st.dataframe(
            audit_log,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No audit events available yet.")


# ------------------------------------------------------------
# SESSION STATE
# ------------------------------------------------------------

if "active_alert_id" not in st.session_state:
    st.session_state.active_alert_id = ""

if "latest_state" not in st.session_state:
    st.session_state.latest_state = None


# ------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------

with st.sidebar:
    st.title("🏦 AML Investigator")
    st.caption("Agentic AI Banking Operations Assistant")

    st.divider()

    st.subheader("Backend Connection")

    health_data, health_error = api_get("/health")

    if health_data:
        st.success("Backend Connected")
        st.caption(
            f"Service: {health_data.get('service', 'AML API')}"
        )
        st.caption(
            f"Version: {health_data.get('version', 'N/A')}"
        )
    else:
        st.error("Backend Offline")
        st.caption(health_error)

    st.divider()

    st.caption("Role A: Agent & Trust Core")
    st.caption("Role B: Data, Platform & Dashboard")


# ------------------------------------------------------------
# MAIN HEADER
# ------------------------------------------------------------

st.title("AML Alert Investigator")
st.write(
    "Investigate suspicious banking activity, inspect evidence, "
    "review AI-generated narratives and record analyst decisions."
)

st.divider()


# ------------------------------------------------------------
# DASHBOARD TABS
# ------------------------------------------------------------

tab1, tab2, tab3 = st.tabs([
    "🔍 New Investigation",
    "🧑‍⚖️ Analyst Review",
    "📂 Retrieve Case"
])


# ============================================================
# TAB 1 — START INVESTIGATION
# ============================================================

with tab1:

    st.header("Start a New Investigation")

    with st.form("investigation_form"):

        alert_id = st.text_input(
            "Alert ID",
            placeholder="Example: ALT-API-001"
        )

        alert_type = st.selectbox(
            "Alert Typology",
            [
                "STRUCTURING",
                "SANCTIONS_MATCH",
                "HIGH_VALUE_TRANSFER"
            ]
        )

        customer_id = st.text_input(
            "Customer ID",
            placeholder="Example: CUST-1001"
        )

        submitted = st.form_submit_button(
            "Run Investigation",
            type="primary",
            use_container_width=True
        )

    if submitted:

        if not alert_id.strip() or not customer_id.strip():
            st.warning("Please enter both Alert ID and Customer ID.")

        else:
            payload = {
                "alert_id": alert_id.strip(),
                "alert_type": alert_type,
                "customer_id": customer_id.strip()
            }

            with st.spinner(
                "Running investigation through the AML agent..."
            ):
                result, error = api_post(
                    "/alerts/investigate",
                    payload
                )

            if error:
                show_api_error(error)

            else:
                st.session_state.active_alert_id = alert_id.strip()
                st.session_state.latest_state = result.get("state", {})

                st.success(
                    result.get(
                        "message",
                        "Investigation request completed."
                    )
                )

                st.info(
                    "Open the Analyst Review tab to inspect the case "
                    "and record a decision if it is awaiting review."
                )

    if st.session_state.latest_state:
        st.divider()
        st.subheader("Latest Investigation Result")
        show_investigation_details(
            st.session_state.latest_state,
            view_id="new_investigation"
        )


# ============================================================
# TAB 2 — HUMAN APPROVAL
# ============================================================

with tab2:

    st.header("Analyst Review & Human Approval")

    review_alert_id = st.text_input(
        "Alert ID to review",
        value=st.session_state.active_alert_id,
        key="review_alert_id"
    )

    if st.button("Load Case for Review", use_container_width=True):

        if not review_alert_id.strip():
            st.warning("Enter an Alert ID first.")

        else:
            result, error = api_get(
                f"/alerts/{review_alert_id.strip()}/state"
            )

            if error:
                show_api_error(error)
            else:
                st.session_state.latest_state = result.get("state", {})
                st.session_state.active_alert_id = review_alert_id.strip()
                st.success("Case loaded successfully.")

    review_state = st.session_state.latest_state

    if (
        review_state
        and review_state.get("alert_id") == review_alert_id.strip()
    ):

        st.divider()
        show_investigation_details(review_state,
                                    view_id="analyst_review"
                                )

        current_status = str(
            review_state.get("status", "")
        ).upper()

        st.divider()
        st.subheader("Human Decision")

        if current_status in {
            "COMPLETED",
            "ESCALATED"
        }:
            st.info(
                f"This case has already reached status: {current_status}. "
                "Check the final case disposition below."
            )

            st.write(
                "**Final disposition:**",
                review_state.get("final_disposition", "Not available")
            )

        else:
            st.warning(
                "Review the evidence and narrative carefully before "
                "submitting your decision."
            )

            with st.form("analyst_decision_form"):

                reviewer_id = st.text_input(
                    "Reviewer ID",
                    value="senior_analyst"
                )

                reviewer_comments = st.text_area(
                    "Reviewer Comments",
                    placeholder="Enter your investigation review comments..."
                )

                edited_note = st.text_area(
                    "Edit Investigation Narrative (optional)",
                    value=str(
                        review_state.get("human_edits")
                        or review_state.get("draft_note", "")
                    ),
                    height=220
                )

                disposition = st.selectbox(
                    "Disposition Override (optional)",
                    [
                        "No override",
                        "FILE_SAR",
                        "REQUEST_RFI",
                        "CLOSE_FALSE_POSITIVE",
                        "ESCALATE_L2"
                    ]
                )

                decision = st.radio(
                    "Analyst Decision",
                    ["Approve", "Reject"],
                    horizontal=True
                )

                confirm = st.form_submit_button(
                    "Submit Final Decision",
                    type="primary",
                    use_container_width=True
                )

            if confirm:

                approval_payload = {
                    "approved": decision == "Approve",
                    "reviewer_id": reviewer_id.strip() or "compliance_analyst",
                    "edited_note": edited_note.strip() or None,
                    "reviewer_comments": reviewer_comments.strip() or None,
                    "disposition_override": (
                        None if disposition == "No override"
                        else disposition
                    )
                }

                with st.spinner("Submitting analyst decision..."):
                    result, error = api_post(
                        f"/alerts/{review_alert_id.strip()}/approve",
                        approval_payload
                    )

                if error:
                    show_api_error(error)

                else:
                    st.success(result.get("message", "Decision submitted."))

                    st.session_state.latest_state = result.get("state", {})
                    st.rerun()


# ============================================================
# TAB 3 — RETRIEVE EXISTING CASE
# ============================================================

with tab3:

    st.header("Retrieve Investigation")

    lookup_alert_id = st.text_input(
        "Enter Alert ID",
        placeholder="Example: ALT-API-001",
        key="lookup_alert_id"
    )

    if st.button("Retrieve Case", use_container_width=True):

        if not lookup_alert_id.strip():
            st.warning("Please enter an Alert ID.")

        else:
            result, error = api_get(
                f"/alerts/{lookup_alert_id.strip()}/state"
            )

            if error:
                show_api_error(error)

            else:
                st.session_state.latest_state = result.get("state", {})
                st.session_state.active_alert_id = lookup_alert_id.strip()

                st.success("Investigation retrieved successfully.")

    retrieved_state = st.session_state.latest_state

    if (
        retrieved_state
        and retrieved_state.get("alert_id") == lookup_alert_id.strip()
    ):
        st.divider()
        show_investigation_details(retrieved_state,
                                   view_id="retrieve_case"
                                )


# ------------------------------------------------------------
# FOOTER
# ------------------------------------------------------------

st.divider()

st.caption(
    "AML Alert Investigator | Agentic AI Banking Operations Assistant | "
    "Human approval is required for final case decisions."
)

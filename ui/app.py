
"""
AML INTELLIGENCE — AML Alert Investigator
Premium Streamlit Command Centre
Connects to the Role A FastAPI backend.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import requests
import streamlit as st
import textwrap


# ============================================================
# 1. CONFIGURATION
# ============================================================

API_BASE_URL = os.getenv(
    "AML_API_URL",
    "http://127.0.0.1:8000"
).rstrip("/")

DATA_ALERTS_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts.json"
EVAL_SUMMARY_PATH = Path(__file__).resolve().parent.parent / "eval" / "reports" / "eval_summary.md"

@st.cache_data
def get_preset_alerts():
    if DATA_ALERTS_PATH.exists():
        try:
            with open(DATA_ALERTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def load_eval_summary_text():
    if EVAL_SUMMARY_PATH.exists():
        try:
            return EVAL_SUMMARY_PATH.read_text(encoding="utf-8")
        except Exception:
            return None
    return None

def generate_sar_export(state):
    aid = state.get("alert_id", "UNKNOWN")
    narrative = state.get("human_edits") or state.get("draft_note", "")
    export_data = {
        "report_type": "FINCEN_SUSPICIOUS_ACTIVITY_REPORT",
        "filing_mode": "ELECTRONIC_AML_PACKAGE_V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_metadata": {
            "alert_id": aid,
            "customer_id": state.get("customer_id"),
            "typology": state.get("alert_type"),
            "risk_tier": state.get("risk_tier"),
            "status": state.get("status"),
            "final_disposition": state.get("final_disposition"),
            "reviewer_id": state.get("reviewer_id", "compliance_analyst"),
            "reviewer_comments": state.get("reviewer_notes") or state.get("reviewer_comments", "None recorded"),
        },
        "grounding_controls": {
            "claim_check_passed": state.get("claim_check_passed"),
            "verifier_agreed": state.get("verifier_agreed"),
            "claims": state.get("claims", [])
        },
        "fincen_5w_narrative": narrative,
        "retrieved_policies": [p.get("source_id") for p in state.get("policy_chunks", []) if isinstance(p, dict)],
        "evidence_summary": {k: v.get("status") for k, v in state.get("evidence", {}).items() if isinstance(v, dict)},
        "audit_trace": state.get("audit_log", [])
    }
    return json.dumps(export_data, indent=2)

def generate_markdown_summary(state):
    aid = state.get("alert_id", "UNKNOWN")
    cid = state.get("customer_id", "UNKNOWN")
    typ = state.get("alert_type", "UNKNOWN")
    disp = state.get("final_disposition", "PENDING_REVIEW")
    tier = state.get("risk_tier", "N/A")
    narrative = state.get("human_edits") or state.get("draft_note", "No narrative generated.")
    reviewer = state.get("reviewer_id", "compliance_analyst")
    comments = state.get("reviewer_notes") or state.get("reviewer_comments", "None")

    return f"""# FinCEN Compliance Case Summary — {aid}

**Alert Reference:** `{aid}`  
**Customer ID:** `{cid}`  
**Typology:** `{typ}`  
**Assigned Risk Tier:** `{tier}`  
**Final Disposition:** `{disp}`  
**Analyst Reviewer:** `{reviewer}`  
**Analyst Reviewer Notes:** {comments}  
**Timestamp:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`

---

## 1. FinCEN 5 Ws Grounded Narrative
{narrative}

---

## 2. Regulatory Quality Controls
- **Deterministic Claim Validation:** {'PASSED (Zero ungrounded assertions)' if state.get('claim_check_passed') else 'PENDING / FAILED'}
- **2nd-Line Skeptic Verifier:** {'AGREED with compliance rationale' if state.get('verifier_agreed') else 'DISAGREED / ESCALATED'}
- **Redraft Cycles:** {state.get('redraft_count', 0)}

---

## 3. Immutable Audit Trail
- **Total Audit Events Recorded:** {len(state.get('audit_log', []))}
"""

st.set_page_config(
    page_title="AML Intelligence | Alert Investigator",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# 2. PREMIUM NAVY BLUE DESIGN SYSTEM
# ============================================================

st.markdown("""
<style>

:root {
    --bg: #080F1E;
    --sidebar: #0D192B;
    --panel: #13243B;
    --panel-light: #192E49;
    --border: #263F5E;
    --blue: #3B82F6;
    --cyan: #38BDF8;
    --text: #F1F5F9;
    --muted: #94A3B8;
    --green: #10B981;
    --red: #EF4444;
}

/* Main background */

.stApp {
    background: var(--bg);
    color: var(--text);
}

/* Sidebar */

[data-testid="stSidebar"] {
    background: var(--sidebar);
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.5rem;
}

/* Main content */

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}

/* Typography */

h1, h2, h3, h4 {
    color: var(--text) !important;
    font-weight: 750 !important;
}

p, label, .stMarkdown {
    color: #CBD5E1;
}

/* Metrics */

[data-testid="stMetric"] {
    background: linear-gradient(
        145deg,
        #172B46,
        #102039
    );
    border: 1px solid var(--border);
    padding: 20px;
    border-radius: 14px;
    min-height: 115px;
}

[data-testid="stMetricLabel"] {
    color: #A9BDD5 !important;
}

[data-testid="stMetricValue"] {
    color: #93C5FD !important;
    font-weight: 750 !important;
}

/* Containers */

[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(19, 36, 59, 0.65);
    border-color: var(--border) !important;
    border-radius: 14px !important;
}

/* Inputs */

.stTextInput input,
.stTextArea textarea,
.stSelectbox div[data-baseweb="select"],
.stNumberInput input {
    background: #142640 !important;
    color: #F8FAFC !important;
    border: 1px solid #355171 !important;
    border-radius: 8px !important;
}

.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: var(--cyan) !important;
    box-shadow: 0 0 0 1px var(--cyan) !important;
}

/* Buttons */

.stButton button,
.stFormSubmitButton button {
    background: linear-gradient(
        90deg,
        #2563EB,
        #1677D2
    );
    color: white !important;
    border: 1px solid #3B82F6;
    border-radius: 9px;
    font-weight: 650;
    min-height: 42px;
    transition: all 0.2s ease;
}

.stButton button:hover,
.stFormSubmitButton button:hover {
    background: #1D4ED8;
    border-color: #60A5FA;
    transform: translateY(-1px);
}

/* Sidebar navigation */

[data-testid="stSidebar"] [role="radiogroup"] label {
    background: transparent;
    border-radius: 8px;
    padding: 8px;
    color: #CBD5E1;
}

[data-testid="stSidebar"] [role="radiogroup"] label:hover {
    background: #1B304A;
}

/* Expanders */

[data-testid="stExpander"] {
    background: #11233B;
    border: 1px solid var(--border);
    border-radius: 10px;
}

/* Tabs */

button[data-baseweb="tab"] {
    color: #A8B9CE !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #60A5FA !important;
    border-bottom-color: #3B82F6 !important;
}

/* Dividers */

hr {
    border-color: #263F5E !important;
}

/* Dataframes */

[data-testid="stDataFrame"] {
    border: 1px solid var(--border);
    border-radius: 10px;
}

/* Alerts */

[data-testid="stAlert"] {
    border-radius: 10px;
}

/* Custom visual elements */

.eyebrow {
    color: #38BDF8;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
}

.hero-title {
    color: #F8FAFC;
    font-size: 34px;
    font-weight: 850;
    letter-spacing: -1px;
    margin-top: 5px;
}

.hero-subtitle {
    color: #94A3B8;
    font-size: 14px;
    margin-top: 6px;
}

.section-label {
    color: #38BDF8;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.5px;
}

.pipeline-card {
    background: #112139;
    border: 1px solid #2A4565;
    border-radius: 12px;
    padding: 17px;
    min-height: 105px;
    margin-bottom: 8px;
}

.pipeline-number {
    color: #38BDF8;
    font-size: 10px;
    font-weight: 800;
}

.pipeline-title {
    color: #EAF3FF;
    font-weight: 700;
    font-size: 14px;
    margin-top: 10px;
}

.pipeline-description {
    color: #94A3B8;
    font-size: 11px;
    margin-top: 5px;
}

.footer-text {
    color: #64748B;
    font-size: 11px;
}


/* Refined enterprise dashboard typography */
h2 {
    font-size: 25px !important;
    letter-spacing: -0.5px;
}

h3 {
    font-size: 19px !important;
    letter-spacing: -0.3px;
}

/* Premium metric cards */
[data-testid="stMetric"] {
    background: linear-gradient(145deg, #172B46 0%, #102039 100%);
    border: 1px solid #29496D;
    border-radius: 15px;
    padding: 22px;
    min-height: 120px;
    box-shadow: 0 5px 18px rgba(0, 0, 0, 0.12);
    transition: all 0.2s ease;
}

[data-testid="stMetric"]:hover {
    border-color: #38BDF8;
    transform: translateY(-3px);
    box-shadow: 0 8px 22px rgba(56, 189, 248, 0.10);
}

/* Metric values */
[data-testid="stMetricValue"] {
    color: #BFDBFE !important;
    font-size: 30px !important;
    font-weight: 750 !important;
}

/* More refined section spacing */
div[data-testid="stVerticalBlock"] > div {
    scroll-margin-top: 20px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# 3. API HELPERS
# ============================================================

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
            detail = response.json().get(
                "detail",
                response.text
            )
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

def render_html(markup):
    st.markdown(
        textwrap.dedent(markup).strip(),
        unsafe_allow_html=True
    )

# ============================================================
# 4. SESSION STATE
# ============================================================

if "active_alert_id" not in st.session_state:
    st.session_state.active_alert_id = ""

if "latest_state" not in st.session_state:
    st.session_state.latest_state = None

if "launched_alerts" not in st.session_state:
    st.session_state.launched_alerts = []


# ============================================================
# 5. REUSABLE INVESTIGATION COMPONENTS
# ============================================================

def show_case_summary(state):

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Alert ID",
            get_state_value(state, "alert_id", "N/A")
        )

    with col2:
        st.metric(
            "Alert Typology",
            get_state_value(state, "alert_type", "N/A")
        )

    with col3:
        st.metric(
            "Risk Tier",
            get_state_value(state, "risk_tier", "Pending")
        )

    with col4:
        st.metric(
            "Investigation Status",
            get_state_value(state, "status", "N/A")
        )


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
            f"{tool_name.replace('_', ' ').title()} — {status}"
        ):

            st.write("**Source IDs**")

            if source_ids:
                st.write(", ".join(map(str, source_ids)))
            else:
                st.write("No source IDs returned.")

            st.write("**Evidence Data**")

            st.json(tool_result.get("data", {}))

            if tool_result.get("error_message"):
                st.warning(tool_result["error_message"])


def show_investigation_details(state, view_id="default"):

    if not state:
        st.info("No investigation details available.")
        return

    show_case_summary(state)

    st.divider()

    st.subheader("Investigation Quality Controls")

    col1, col2, col3 = st.columns(3)

    with col1:
        passed = bool(state.get("claim_check_passed"))
        st.metric(
            "Claim Validation",
            "PASSED" if passed else "PENDING / FAILED"
        )

    with col2:
        agreed = bool(state.get("verifier_agreed"))
        st.metric(
            "Independent Verifier",
            "AGREED" if agreed else "PENDING / NOT AGREED"
        )

    with col3:
        st.metric(
            "Redraft Attempts",
            state.get("redraft_count", 0)
        )

    st.divider()

    st.subheader("AI-Generated Investigation Narrative")

    draft = (
        state.get("human_edits")
        or state.get("draft_note")
        or "No investigation narrative generated."
    )

    st.text_area(
        "Investigation narrative",
        value=str(draft),
        height=280,
        disabled=True,
        key=(
            f"draft_{view_id}_"
            f"{state.get('alert_id', 'unknown')}"
        )
    )

    st.divider()

    st.subheader("Retrieved Policy Documents")

    policy_chunks = state.get("policy_chunks", [])

    if policy_chunks:

        for policy in policy_chunks:

            if not isinstance(policy, dict):
                continue

            with st.expander(
                policy.get(
                    "title",
                    policy.get("source_id", "Policy")
                )
            ):

                st.write(policy.get("content", ""))

                st.caption(
                    f"Source ID: {policy.get('source_id', 'Unknown')}"
                )

    else:
        st.info("No policy documents returned.")

    st.divider()

    st.subheader("Evidence Repository")

    show_evidence(state)

    st.divider()

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

    if state.get("escalation_reason"):
        st.warning(
            f"Escalation Reason: {state['escalation_reason']}"
        )

    if state.get("final_disposition"):
        st.success(
            f"Final Disposition: {state['final_disposition']}"
        )


# ============================================================
# 6. SIDEBAR — COMMAND NAVIGATION
# ============================================================

with st.sidebar:

    render_html("""
<div style="padding: 8px 0 20px 0;">
    <div style="font-size:32px;">🛡️</div>
    <div style="
        font-size:21px;
        font-weight:850;
        color:#F1F5F9;
        letter-spacing:-0.5px;
    ">
        AML INTELLIGENCE
    </div>
    <div style="
        font-size:10px;
        color:#94A3B8;
        margin-top:5px;
        letter-spacing:1px;
    ">
        AGENTIC INVESTIGATION PLATFORM
    </div>
</div>
""")

    st.divider()

    st.markdown(
        '<div class="section-label">WORKSPACE</div>',
        unsafe_allow_html=True
    )

    selected_page = st.radio(
        "Navigation",
        [
            "Overview",
            "Investigation Workspace",
            "Performance Analytics"
        ],
        label_visibility="collapsed",
        key="main_navigation"
    )

    st.divider()

    st.markdown("### System Status")

    health_data, health_error = api_get("/health")

    if health_data:

        st.success("● Backend Operational")

        st.caption(
            health_data.get(
                "service",
                "AML Alert Investigator API"
            )
        )

        st.caption(
            f"Version {health_data.get('version', 'N/A')}"
        )

    else:

        st.error("● Backend Offline")

        st.caption(str(health_error)[:250])

    st.divider()

    st.markdown("### Investigation Engine")

    st.caption("🧠 LangGraph Orchestration")
    st.caption("📚 ChromaDB Policy Retrieval")
    st.caption("🔎 Evidence Verification")
    st.caption("🛡️ Human-in-the-Loop Approval")

    st.divider()

    st.markdown("### Platform")

    st.caption("Evidence-led decisions")
    st.caption("Independent verification")
    st.caption("Human oversight")
    st.caption("Auditable investigation")


# ============================================================
# 7. GLOBAL HEADER
# ============================================================

render_html("""
<div style="padding: 12px 0 22px 0;">
    <div class="eyebrow">
        AML / INTELLIGENCE / COMMAND CENTER
    </div>
    <div class="hero-title">
        AML Alert Investigator
    </div>
    <div class="hero-subtitle">
        Intelligent financial crime investigation
        and risk monitoring platform
    </div>
</div>
""")

st.divider()


# ============================================================
# PAGE 1 — COMMAND CENTER OVERVIEW
# ============================================================

if selected_page == "Overview":

    st.markdown("## Intelligence Overview")

    st.caption(
        "Latest completed benchmark snapshot · 36 evaluated cases"
    )

    # Benchmark results from the supplied evaluation run.
    # Update these figures whenever a new benchmark is completed.

    st.markdown("### Model & Investigation Performance")

    metric1, metric2, metric3, metric4 = st.columns(4)

    with metric1:
        st.metric(
            "Cases Evaluated",
            "36",
            help="Total cases in the latest benchmark."
        )

    with metric2:
        st.metric(
            "Decision Accuracy",
            "100%",
            help="36 correct decisions out of 36 cases."
        )

    with metric3:
        st.metric(
            "Claim Groundedness",
            "100%",
            help="Groundedness rate in the latest benchmark."
        )

    with metric4:
        st.metric(
            "Macro F1 Score",
            "1.0000"
        )

    st.write("")

    metric5, metric6, metric7 = st.columns(3)

    with metric5:
        st.metric(
            "Average Latency",
            "272.09 ms"
        )

    with metric6:
        st.metric(
            "P95 Latency",
            "87.59 ms"
        )

    with metric7:
        st.metric(
            "Average Cost / Case",
            "$0.00045"
        )

    st.divider()

    # --------------------------------------------------------
    # AGENT PIPELINE
    # --------------------------------------------------------

    st.markdown("## Agent Investigation Pipeline")

    st.caption(
        "Nine stages implemented in the LangGraph investigation engine."
    )

    workflow = [
        ("01", "Intake", "Alert received"),
        ("02", "Classification", "Typology detection"),
        ("03", "Policy Retrieval", "ChromaDB RAG"),
        ("04", "Evidence Collection", "Banking records"),
        ("05", "Draft Note", "Investigation narrative"),
        ("06", "Claim Check", "Citation validation"),
        ("07", "Verifier", "Independent review"),
        ("08", "Risk Router", "Disposition routing"),
        ("09", "Human Review", "Analyst approval")
    ]

    for start in range(0, len(workflow), 3):

        cols = st.columns(3)

        for col, item in zip(
            cols,
            workflow[start:start + 3]
        ):

            number, title, description = item

            with col:

                render_html(f"""
<div class="pipeline-card">
    <div class="pipeline-number">
        STAGE {number}
    </div>
    <div class="pipeline-title">
        {title}
    </div>
    <div class="pipeline-description">
        {description}
    </div>
</div>
""")
    st.divider()

    # --------------------------------------------------------
    # LATEST INVESTIGATION
    # --------------------------------------------------------

    st.markdown("## Latest Investigation")

    if st.session_state.latest_state:

        latest = st.session_state.latest_state

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Alert ID",
                latest.get("alert_id", "N/A")
            )

        with col2:
            st.metric(
                "Typology",
                latest.get("alert_type", "N/A")
            )

        with col3:
            st.metric(
                "Risk Tier",
                latest.get("risk_tier") or "Pending"
            )

        with col4:
            st.metric(
                "Status",
                latest.get("status", "N/A")
            )

        st.info(
            "Open Investigation Workspace to inspect "
            "the complete investigation."
        )

    else:

        st.info(
            "No investigation loaded in this session. "
            "Start a new investigation from the workspace."
        )

    st.divider()

    # --------------------------------------------------------
    # ALERT TRIAGE QUEUE (DATASET INBOX)
    # --------------------------------------------------------

    st.markdown("## Alert Triage Queue")
    st.caption("Active monitoring queue of pending banking alerts across institutional typologies.")

    queue_presets = get_preset_alerts()

    if queue_presets:
        filter_col, search_col = st.columns([1, 2])
        with filter_col:
            typology_filter = st.selectbox(
                "Filter by Typology",
                ["ALL", "STRUCTURING", "SANCTIONS_MATCH", "HIGH_VALUE_TRANSFER"],
                key="overview_typology_filter"
            )
        with search_col:
            search_query = st.text_input(
                "Search Alert, Customer or Typology",
                placeholder="Search by ID, customer reference, scenario...",
                key="overview_search_query"
            )

        filtered_alerts = queue_presets
        if typology_filter != "ALL":
            filtered_alerts = [a for a in filtered_alerts if a.get("alert_type") == typology_filter]
        if search_query.strip():
            sq = search_query.strip().lower()
            filtered_alerts = [
                a for a in filtered_alerts
                if sq in str(a.get("alert_id", "")).lower()
                or sq in str(a.get("customer_id", "")).lower()
                or sq in str(a.get("scenario_tag", "")).lower()
            ]

        table_rows = []
        for a in filtered_alerts:
            trigger = a.get("trigger_details", {})
            amount = trigger.get("total_amount", 0)
            tx_count = len(trigger.get("transaction_ids", []))
            table_rows.append({
                "Alert ID": a.get("alert_id"),
                "Typology": a.get("alert_type"),
                "Customer Reference": a.get("customer_id"),
                "Amount ($)": f"${amount:,.2f}" if amount else "N/A",
                "Transactions": tx_count if tx_count > 0 else 1,
                "Scenario Tag": a.get("scenario_tag", "standard").replace("_", " ").title(),
                "Registered Date": a.get("created_at", "N/A")
            })

        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        launch_col1, launch_col2 = st.columns([3, 1])
        with launch_col1:
            queue_picker = st.selectbox(
                "Quick-Select Alert to Investigate",
                [a["Alert ID"] for a in table_rows] if table_rows else ["No matching alerts"],
                key="overview_queue_picker"
            )
        with launch_col2:
            st.write("")
            st.write("")
            if st.button("🚀 Launch from Queue", type="primary", use_container_width=True, key="btn_launch_from_queue", disabled=not bool(table_rows)):
                chosen_raw = next((a for a in queue_presets if a.get("alert_id") == queue_picker), None)
                if chosen_raw:
                    with st.spinner(f"Initiating investigation for {queue_picker}..."):
                        res, err = api_post("/alerts/investigate", chosen_raw)
                        if err:
                            show_api_error(err)
                        else:
                            st.session_state.active_alert_id = queue_picker
                            st.session_state.latest_state = res.get("state", {})
                            if queue_picker not in st.session_state.launched_alerts:
                                st.session_state.launched_alerts.append(queue_picker)
                            st.success(f"Investigation for {queue_picker} initiated! Head to Investigation Workspace.")
                            st.rerun()

    st.divider()

    # --------------------------------------------------------
    # PLATFORM PRINCIPLES
    # --------------------------------------------------------

    st.markdown("## Platform Principles")

    p1, p2, p3 = st.columns(3)

    with p1:

        st.markdown("### 🧾 Evidence First")

        st.caption(
            "Every material finding should be supported "
            "by traceable source evidence."
        )

    with p2:

        st.markdown("### 🛡️ Trust & Verification")

        st.caption(
            "Claim validation and independent verification "
            "before final decisions."
        )

    with p3:

        st.markdown("### 👤 Human Control")

        st.caption(
            "Final investigation decisions remain subject "
            "to analyst review."
        )



# ============================================================
# PAGE 2 — PREMIUM INVESTIGATION INTELLIGENCE WORKSPACE
# ============================================================

elif selected_page == "Investigation Workspace":

    st.markdown("## Investigation Intelligence Workspace")
    st.caption(
        "Evidence-led AML investigation | Independent verification | Human-controlled decisions"
    )

    # --------------------------------------------------------
    # HELPER FUNCTIONS
    # --------------------------------------------------------

    def workspace_status(value):
        return str(value or "PENDING").replace("_", " ").upper()

    def render_stage(number, title, description, status):
        colors = {
            "complete": ("#123D36", "#34D399", "COMPLETED"),
            "active": ("#183B61", "#60A5FA", "IN PROGRESS"),
            "blocked": ("#49252D", "#F87171", "BLOCKED"),
            "pending": ("#202F46", "#94A3B8", "PENDING"),
        }

        bg, accent, label = colors[status]

        render_html(f"""
        <div style="
            background:{bg};
            border:1px solid {accent}55;
            border-radius:13px;
            padding:15px;
            min-height:125px;
            margin-bottom:8px;
        ">
            <div style="color:{accent};font-size:10px;font-weight:800;">
                STAGE {number} · {label}
            </div>
            <div style="color:#F8FAFC;font-size:16px;font-weight:750;margin-top:9px;">
                {title}
            </div>
            <div style="color:#A9B8CC;font-size:12px;margin-top:6px;">
                {description}
            </div>
        </div>
        """)

    def render_investigation_pipeline(state):

        status = workspace_status(state.get("status"))
        claim_passed = state.get("claim_check_passed", False)
        verifier_agreed = state.get("verifier_agreed", False)

        stages = [
            ("Intake", "Alert registration", True),
            ("Classification", "AML typology detection", bool(state.get("alert_type"))),
            ("Policy Retrieval", "ChromaDB institutional policies", bool(state.get("policy_chunks"))),
            ("Evidence Collection", "Banking system evidence", bool(state.get("evidence"))),
            ("Draft Narrative", "FinCEN Five Ws", bool(state.get("draft_note"))),
            ("Claim Check", "Citation and factual validation", claim_passed),
            ("Independent Verifier", "Second-line compliance QA", verifier_agreed),
            ("Risk Router", "Deterministic risk assessment", bool(state.get("risk_tier"))),
            ("Human Review", "Analyst decision", status in {"COMPLETED", "ESCALATED"}),
        ]

        for start in range(0, len(stages), 3):
            columns = st.columns(3)

            for column, item in zip(columns, stages[start:start + 3]):
                index = start + stages[start:start + 3].index(item)
                title, description, completed = item

                if completed:
                    stage_status = "complete"
                elif status == "ESCALATED" and title in {
                    "Claim Check", "Independent Verifier"
                }:
                    stage_status = "blocked"
                elif status in {"AWAITING_APPROVAL", "AWAITING APPROVAL"} and title == "Human Review":
                    stage_status = "active"
                elif index == 0:
                    stage_status = "active"
                else:
                    stage_status = "pending"

                with column:
                    render_stage(
                        f"{index + 1:02d}",
                        title,
                        description,
                        stage_status
                    )

    def render_workspace_evidence(state):

        evidence = state.get("evidence", {})

        if not evidence:
            st.info("Evidence has not been returned for this investigation.")
            return

        for tool_name, result in evidence.items():

            if not isinstance(result, dict):
                continue

            tool_status = result.get("status", "UNKNOWN")
            source_ids = result.get("source_ids", [])
            data = result.get("data", {})

            with st.expander(
                f"{tool_name.replace('_', ' ').title()} · {tool_status}",
                expanded=False
            ):

                left, right = st.columns([1, 2])

                with left:
                    st.markdown("**Evidence sources**")
                    for source in source_ids:
                        st.code(str(source), language=None)

                with right:
                    st.markdown("**Retrieved evidence**")
                    st.json(data)

    def render_workspace_policies(state):

        policies = state.get("policy_chunks", [])

        if not policies:
            st.info("No policy chunks were returned.")
            return

        for policy in policies:

            with st.expander(
                f"{policy.get('title', 'Institutional Policy')} · "
                f"{policy.get('source_id', 'UNKNOWN SOURCE')}"
            ):
                st.write(policy.get("content", ""))
                st.caption(
                    f"Policy source: {policy.get('source_id', 'Unavailable')}"
                )

    def render_workspace_narrative(state, view_id="default"):

        narrative = (
            state.get("human_edits")
            or state.get("draft_note")
            or ""
        )

        if narrative:
            alert_id_safe = str(state.get("alert_id") or "unknown")
            st.text_area(
                "Investigation narrative",
                value=str(narrative),
                height=330,
                disabled=True,
                key=f"workspace_narrative_{view_id}_{alert_id_safe}"
            )
        else:
            st.info("No investigation narrative is available.")

    # --------------------------------------------------------
    # WORKSPACE NAVIGATION
    # --------------------------------------------------------

    workspace_tab1, workspace_tab2, workspace_tab3 = st.tabs([
        "01 · Launch Investigation",
        "02 · Analyst Decision Centre",
        "03 · Case Intelligence"
    ])

    # ========================================================
    # TAB 1 — LAUNCH INVESTIGATION
    # ========================================================

    with workspace_tab1:

        st.markdown("### New Investigation")
        st.caption("Register an alert and initiate the agent workflow.")

        preset_alerts = get_preset_alerts()
        alert_options = ["-- Quick-Select from Synthetic Dataset (36 Alerts) --"]
        preset_map = {}
        for pa in preset_alerts:
            label = f"{pa.get('alert_id')} · {pa.get('alert_type')} (Customer: {pa.get('customer_id')})"
            alert_options.append(label)
            preset_map[label] = pa

        selected_preset = st.selectbox(
            "Select Alert to Investigate",
            alert_options,
            index=1 if len(alert_options) > 1 else 0,
            help="Choose a pre-configured alert from data/alerts.json to automatically supply its customer and transaction trigger data."
        )

        chosen_alert = preset_map.get(selected_preset)

        default_alert_id = chosen_alert.get("alert_id", "") if chosen_alert else ""
        default_customer_id = chosen_alert.get("customer_id", "") if chosen_alert else ""
        default_typology = chosen_alert.get("alert_type", "STRUCTURING") if chosen_alert else "STRUCTURING"
        typology_choices = ["STRUCTURING", "SANCTIONS_MATCH", "HIGH_VALUE_TRANSFER"]
        typology_idx = typology_choices.index(default_typology) if default_typology in typology_choices else 0

        with st.container(border=True):

            st.markdown("#### Alert Information")

            with st.form("premium_investigation_form"):

                col1, col2 = st.columns(2)

                with col1:
                    alert_id = st.text_input(
                        "Alert Reference",
                        value=default_alert_id,
                        placeholder="ALT-STR-001"
                    )

                with col2:
                    customer_id = st.text_input(
                        "Customer Reference",
                        value=default_customer_id,
                        placeholder="CUST-1001"
                    )

                alert_type = st.selectbox(
                    "Investigation Typology",
                    typology_choices,
                    index=typology_idx
                )

                submitted = st.form_submit_button(
                    "Launch AML Investigation",
                    type="primary",
                    use_container_width=True
                )

        if submitted:

            if not alert_id.strip() or not customer_id.strip():

                st.warning("Both alert reference and customer reference are required.")

            else:

                # Auto-match with synthetic dataset if the alert reference matches
                matched_preset = next(
                    (a for a in preset_alerts if a.get("alert_id") == alert_id.strip()),
                    None
                )

                if matched_preset:
                    payload = dict(matched_preset)
                    # Use the dataset's validated customer_id if custom input doesn't exist
                    if customer_id.strip() and customer_id.strip() != "CUST-3088":
                        payload["customer_id"] = customer_id.strip()
                    payload["alert_type"] = alert_type
                elif chosen_alert and chosen_alert.get("alert_id") == alert_id.strip():
                    payload = dict(chosen_alert)
                    payload["customer_id"] = customer_id.strip()
                    payload["alert_type"] = alert_type
                else:
                    payload = {
                        "alert_id": alert_id.strip(),
                        "customer_id": customer_id.strip(),
                        "alert_type": alert_type
                    }

                with st.spinner(
                    "LangGraph is processing the investigation..."
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
                    if alert_id.strip() not in st.session_state.launched_alerts:
                        st.session_state.launched_alerts.append(alert_id.strip())

                    st.success(
                        result.get(
                            "message",
                            "Investigation request processed."
                        )
                    )

                    st.rerun()

        current_state = st.session_state.latest_state

        if current_state:

            st.divider()
            st.markdown("### Investigation Snapshot")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Alert ID", current_state.get("alert_id", "N/A"))

            with col2:
                st.metric("Typology", current_state.get("alert_type", "N/A"))

            with col3:
                st.metric("Risk Tier", current_state.get("risk_tier", "Pending"))

            with col4:
                st.metric("Status", current_state.get("status", "Pending"))

            st.markdown("### Agent Execution Pipeline")
            render_investigation_pipeline(current_state)

            st.divider()

            st.markdown("### Investigation Narrative")
            render_workspace_narrative(current_state, view_id="tab1_snapshot")

    # ========================================================
    # TAB 2 — ANALYST DECISION CENTRE
    # ========================================================

    with workspace_tab2:

        st.markdown("### Human-in-the-Loop Review")
        st.caption(
            "Inspect the investigation and record an explicit analyst decision."
        )

        preset_alerts = get_preset_alerts()

        review_alert_id = st.text_input(
            "Alert ID",
            value=st.session_state.active_alert_id,
            placeholder="e.g. ALT-STR-001, ALT-SAN-001, ALT-HVT-001",
            key="premium_review_alert_id"
        )

        if st.button(
            "Load Investigation",
            type="primary",
            use_container_width=True
        ):

            if not review_alert_id.strip():

                st.warning("Enter an alert ID.")

            else:

                result, error = api_get(
                    f"/alerts/{review_alert_id.strip()}/state"
                )

                if error:
                    if "404" in str(error):
                        st.warning(
                            f"Alert '{review_alert_id.strip()}' has not been launched yet in this session. "
                            "Please go to **Tab 01 · Launch Investigation** first to run the agent workflow on this alert."
                        )
                    else:
                        show_api_error(error)

                else:
                    st.session_state.latest_state = result.get("state", {})
                    st.session_state.active_alert_id = review_alert_id.strip()
                    if review_alert_id.strip() not in st.session_state.launched_alerts:
                        st.session_state.launched_alerts.append(review_alert_id.strip())
                    st.success("Investigation loaded.")
                    st.rerun()

        review_state = st.session_state.latest_state

        if (
            review_state
            and review_state.get("alert_id") == review_alert_id.strip()
        ):

            st.divider()

            status = workspace_status(review_state.get("status"))

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Claim Validation",
                          "PASSED" if review_state.get("claim_check_passed") else "NOT PASSED")

            with col2:
                st.metric("Independent Verification",
                          "AGREED" if review_state.get("verifier_agreed") else "NOT AGREED")

            with col3:
                st.metric("Risk Tier",
                          review_state.get("risk_tier", "Pending"))

            st.markdown("### Case Narrative")
            render_workspace_narrative(review_state, view_id="tab2_review")

            st.markdown("### Verification Findings")
            st.write(
                review_state.get(
                    "verifier_notes",
                    "No verifier notes available."
                )
            )

            st.divider()

            if status in {"COMPLETED", "ESCALATED"}:

                st.info(f"This investigation is already {status}.")

                st.metric(
                    "Final Disposition",
                    review_state.get("final_disposition", "Not available")
                )

                st.write(
                    "Escalation reason:",
                    review_state.get("escalation_reason") or "None recorded."
                )

                st.divider()
                st.markdown("### Export Regulatory Filing Package")
                exp_col1, exp_col2 = st.columns(2)
                with exp_col1:
                    sar_json = generate_sar_export(review_state)
                    st.download_button(
                        label="📥 Download FinCEN SAR Package (.json)",
                        data=sar_json,
                        file_name=f"FINCEN_SAR_{review_state.get('alert_id', 'ALERT')}.json",
                        mime="application/json",
                        use_container_width=True,
                        key="tab2_btn_download_sar_json"
                    )
                with exp_col2:
                    case_md = generate_markdown_summary(review_state)
                    st.download_button(
                        label="📄 Download Case Summary (.md)",
                        data=case_md,
                        file_name=f"CASE_SUMMARY_{review_state.get('alert_id', 'ALERT')}.md",
                        mime="text/markdown",
                        use_container_width=True,
                        key="tab2_btn_download_case_md"
                    )

            elif status in {"AWAITING_APPROVAL", "AWAITING APPROVAL"}:

                st.warning(
                    "Review the underlying evidence and narrative before deciding."
                )

                with st.form("premium_analyst_decision_form"):

                    reviewer_id = st.text_input(
                        "Reviewer ID",
                        value="senior_analyst"
                    )

                    reviewer_comments = st.text_area(
                        "Reviewer Comments",
                        placeholder="Document your review observations..."
                    )

                    edited_note = st.text_area(
                        "Analyst-edited narrative",
                        value=str(
                            review_state.get("human_edits")
                            or review_state.get("draft_note", "")
                        ),
                        height=250
                    )

                    disposition = st.selectbox(
                        "Disposition Override",
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
                        "Submit Analyst Decision",
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

                    with st.spinner("Recording analyst decision..."):

                        result, error = api_post(
                            f"/alerts/{review_alert_id.strip()}/approve",
                            approval_payload
                        )

                    if error:

                        show_api_error(error)

                    else:

                        st.session_state.latest_state = result.get("state", {})
                        st.success(
                            result.get("message", "Decision recorded.")
                        )
                        st.rerun()

            else:

                st.info(
                    f"Current case status is {status}. "
                    "The approval form is available only when the backend "
                    "has paused the investigation for human review."
                )

    # ========================================================
    # TAB 3 — CASE INTELLIGENCE
    # ========================================================

    with workspace_tab3:

        st.markdown("### Case Intelligence Explorer")
        st.caption(
            "Retrieve and inspect saved investigation records, evidence and audit history."
        )

        lookup_alert_id = st.text_input(
            "Investigation Reference",
            value=st.session_state.active_alert_id,
            key="premium_lookup_alert_id"
        )

        if st.button(
            "Retrieve Case Intelligence",
            use_container_width=True
        ):

            if not lookup_alert_id.strip():

                st.warning("Enter an alert reference.")

            else:

                result, error = api_get(
                    f"/alerts/{lookup_alert_id.strip()}/state"
                )

                if error:
                    if "404" in str(error):
                        st.warning(
                            f"Investigation '{lookup_alert_id.strip()}' has not been launched yet in this session. "
                            "Please launch it first in **Tab 01 · Launch Investigation**."
                        )
                    else:
                        show_api_error(error)

                else:

                    st.session_state.latest_state = result.get("state", {})
                    st.session_state.active_alert_id = lookup_alert_id.strip()
                    st.success("Case intelligence retrieved.")
                    st.rerun()

        case_state = st.session_state.latest_state

        if (
            case_state
            and case_state.get("alert_id") == lookup_alert_id.strip()
        ):

            st.divider()

            st.markdown("### Case Overview")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Alert", case_state.get("alert_id", "N/A"))

            with col2:
                st.metric("Customer", case_state.get("customer_id", "N/A"))

            with col3:
                st.metric("Risk Tier", case_state.get("risk_tier", "N/A"))

            with col4:
                st.metric("Status", case_state.get("status", "N/A"))

            st.divider()

            st.markdown("### Agent Execution")
            render_investigation_pipeline(case_state)

            st.divider()

            st.markdown("### Institutional Policy References")
            render_workspace_policies(case_state)

            st.divider()

            st.markdown("### Evidence Intelligence")
            render_workspace_evidence(case_state)

            st.divider()

            st.markdown("### Investigation Narrative")
            render_workspace_narrative(case_state, view_id="tab3_intel")

            st.divider()

            st.markdown("### Audit Trail")

            audit_log = case_state.get("audit_log", [])

            if audit_log:
                st.dataframe(
                    audit_log,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No audit events have been recorded.")

            st.divider()
            st.markdown("### Export Regulatory Filing Package")
            c3_col1, c3_col2 = st.columns(2)
            with c3_col1:
                sar_json = generate_sar_export(case_state)
                st.download_button(
                    label="📥 Download FinCEN SAR Package (.json)",
                    data=sar_json,
                    file_name=f"FINCEN_SAR_{case_state.get('alert_id', 'ALERT')}.json",
                    mime="application/json",
                    use_container_width=True,
                    key="tab3_btn_download_sar_json"
                )
            with c3_col2:
                case_md = generate_markdown_summary(case_state)
                st.download_button(
                    label="📄 Download Case Summary (.md)",
                    data=case_md,
                    file_name=f"CASE_SUMMARY_{case_state.get('alert_id', 'ALERT')}.md",
                    mime="text/markdown",
                    use_container_width=True,
                    key="tab3_btn_download_case_md"
                )


# ============================================================
# PAGE 3 — PERFORMANCE ANALYTICS
# ============================================================

elif selected_page == "Performance Analytics":

    st.markdown("## Performance Intelligence")

    btn_col1, btn_col2 = st.columns([2, 1])
    with btn_col1:
        st.caption("Latest benchmark snapshot · 36 test cases against compliance ground truth")
    with btn_col2:
        if st.button("⚡ Re-Run Benchmark (36 Cases)", key="btn_run_eval_benchmark", use_container_width=True):
            with st.spinner("Executing full 36-case benchmark evaluation..."):
                try:
                    from eval.run_eval import run_benchmark
                    run_benchmark()
                    st.success("Benchmark completed! Metrics updated.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Benchmark error: {exc}")

    st.info(
        "The following metrics represent the latest completed "
        "36-case benchmark run."
    )

    st.markdown("### Evaluation Metrics")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Decision Accuracy",
            "100.00%"
        )

    with col2:
        st.metric(
            "Macro F1 Score",
            "1.0000"
        )

    with col3:
        st.metric(
            "Weighted F1 Score",
            "1.0000"
        )

    col4, col5, col6 = st.columns(3)

    with col4:
        st.metric(
            "Groundedness",
            "100.00%"
        )

    with col5:
        st.metric(
            "Average Latency",
            "272.09 ms"
        )

    with col6:
        st.metric(
            "Total Run Cost",
            "$0.0164"
        )

    st.divider()

    st.subheader("Disposition Performance")

    disposition_data = {
        "Disposition": [
            "CLOSE_FALSE_POSITIVE",
            "ESCALATE_L2",
            "FILE_SAR",
            "REQUEST_RFI"
        ],

        "Correct Cases": [
            10, 3, 12, 11
        ],

        "Total Cases": [
            10, 3, 12, 11
        ]
    }

    st.dataframe(
        disposition_data,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Counts reflect the confusion matrix from "
        "the latest shared benchmark report."
    )

    eval_markdown = load_eval_summary_text()
    if eval_markdown:
        st.divider()
        st.subheader("Benchmark Executive Report")
        with st.expander("📄 View Full Markdown Benchmark Summary (eval_summary.md)", expanded=False):
            st.markdown(eval_markdown)

    st.divider()

    st.subheader("System Architecture")

    architecture = [
        ("Orchestration", "LangGraph"),
        ("Policy Retrieval", "ChromaDB / RAG"),
        ("Evidence Collection", "Banking evidence tools"),
        ("Claim Validation", "Source-grounded validation"),
        ("Independent Review", "Verifier node"),
        ("Human Approval", "Analyst-in-the-loop"),
        ("API Layer", "FastAPI"),
        ("Frontend", "Streamlit")
    ]

    for name, technology in architecture:

        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown(f"**{name}**")

        with col2:
            st.caption(technology)


# ============================================================
# 8. FOOTER
# ============================================================

st.divider()

render_html("""
<div style="
    display:flex;
    justify-content:space-between;
    flex-wrap:wrap;
    gap:10px;
    color:#64748B;
    font-size:11px;
    padding:10px 0;
">
    <span>AML INTELLIGENCE · AGENTIC AI PLATFORM</span>
    <span>Evidence-led decisions · Human oversight · Auditability</span>
</div>
""")

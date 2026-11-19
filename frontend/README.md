# AML Intelligence — Modern Web Frontend

A compliance analyst workbench built for the **AML Alert Investigator** agentic platform.

---

## 🚀 How to Run the Frontend

You can run this frontend in **two ways**:

### Option 1: Direct via FastAPI Backend (Fastest & Zero Setup)
The FastAPI backend serves this dashboard directly at root:
1. Start the API:
   ```bash
   uvicorn app.api:app --reload --port 8000
   ```
2. Open your browser:
   **[http://localhost:8000/](http://localhost:8000/)** or **[http://localhost:8000/app](http://localhost:8000/app)**

### Option 2: Standalone Browser Launch
Open `frontend/index.html` directly in any modern web browser (Chrome, Edge, Firefox). It automatically connects to `http://127.0.0.1:8000`.

---

## 🛡️ Key Features

- **Alert Triage Inbox**: Search, filter, and review all 36 alerts from the synthetic core banking dataset.
- **Investigation Workbench**:
  - 9-stage visual execution pipeline stepper (Intake &rarr; Human Review).
  - Split-screen layout:
    - **Evidence Repository**: KYC Profile, Core Banking Ledger, OFAC/PEP Watchlist Screening, and Institutional Policy chunks.
    - **FinCEN 5 Ws Narrative**: AI-synthesized narrative with sentence-level `[SRC:...]` citation badges.
    - **Human-in-the-Loop Decision Center**: Approve, Reject, or Override disposition with comments.
- **Regulatory Exports**: 1-click download of the complete **FinCEN SAR Package (.json)** and **Markdown Case Dossier (.md)**.
- **Performance Analytics**: Live evaluation benchmark telemetry, confusion matrix, and regulatory guardrail summaries.

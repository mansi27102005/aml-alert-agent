# AML Alert Investigator - Evaluation Benchmark Report

**Execution Timestamp:** `2026-11-18T05:29:03.669581+00:00`  
**Total Cases Evaluated:** `36` alerts across Structuring, Sanctions, and High-Value Transfers  
**Overall Decision Accuracy:** `100.00%`  
**Overall Claim Groundedness:** `100.00%`  

---

## 1. Executive Summary & Core KPIs

| Metric | Result | Benchmark Target | Compliance Threshold | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Decision Accuracy** | **100.0%** | > 90.0% | 85.0% | PASS |
| **Macro F1 Score** | **1.0000** | > 0.8800 | 0.8000 | PASS |
| **Weighted F1 Score** | **1.0000** | > 0.9000 | 0.8500 | PASS |
| **Sentence Groundedness** | **100.0%** | 100.0% | 98.0% | PASS |
| **P95 Latency** | **87.6 ms** | < 2,500 ms | 5,000 ms | PASS |
| **Average Cost per Case** | **$0.00045** | < $0.05 | $0.10 | PASS |

---

## 2. Multi-Class Performance Breakdown

| Disposition Class | Precision | Recall | F1 Score | Support (Count) |
| :--- | :--- | :--- | :--- | :--- |
| `CLOSE_FALSE_POSITIVE` | 1.0000 | 1.0000 | 1.0000 | 10 |
| `ESCALATE_L2` | 1.0000 | 1.0000 | 1.0000 | 3 |
| `FILE_SAR` | 1.0000 | 1.0000 | 1.0000 | 12 |
| `REQUEST_RFI` | 1.0000 | 1.0000 | 1.0000 | 11 |

### Confusion Matrix

| Actual \ Predicted | `CLOSE_FALSE_POSITIVE` | `ESCALATE_L2` | `FILE_SAR` | `REQUEST_RFI` |
| :--- | :---: | :---: | :---: | :---: |
| `CLOSE_FALSE_POSITIVE` | 10 | 0 | 0 | 0 |
| `ESCALATE_L2` | 0 | 3 | 0 | 0 |
| `FILE_SAR` | 0 | 0 | 12 | 0 |
| `REQUEST_RFI` | 0 | 0 | 0 | 11 |

---

## 3. Operational & Cost Telemetry

- **Average Latency:** 272.09 ms
- **P95 Latency:** 87.59 ms
- **Max Latency:** 7880.78 ms
- **Average Tokens Used:** 5235.0 tokens/case
- **Total Estimated Cost:** $0.0164

---

## 4. Case-by-Case Audit Trail

| Alert ID | Typology | Expected | Predicted | Match | Groundedness | Latency (ms) | Tokens |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `ALT-STR-001` | STRUCTURING | `FILE_SAR` | `FILE_SAR` | YES | 100% | 7880.8 | 5684 |
| `ALT-STR-002` | STRUCTURING | `FILE_SAR` | `FILE_SAR` | YES | 100% | 57.6 | 5687 |
| `ALT-STR-003` | STRUCTURING | `FILE_SAR` | `FILE_SAR` | YES | 100% | 87.6 | 5686 |
| `ALT-STR-004` | STRUCTURING | `FILE_SAR` | `FILE_SAR` | YES | 100% | 61.9 | 5684 |
| `ALT-STR-005` | STRUCTURING | `FILE_SAR` | `FILE_SAR` | YES | 100% | 52.9 | 5709 |
| `ALT-STR-006` | STRUCTURING | `REQUEST_RFI` | `REQUEST_RFI` | YES | 100% | 48.8 | 5427 |
| `ALT-STR-007` | STRUCTURING | `REQUEST_RFI` | `REQUEST_RFI` | YES | 100% | 55.1 | 5435 |
| `ALT-STR-008` | STRUCTURING | `REQUEST_RFI` | `REQUEST_RFI` | YES | 100% | 51.4 | 5431 |
| `ALT-STR-009` | STRUCTURING | `CLOSE_FALSE_POSITIVE` | `CLOSE_FALSE_POSITIVE` | YES | 100% | 50.8 | 5523 |
| `ALT-STR-010` | STRUCTURING | `CLOSE_FALSE_POSITIVE` | `CLOSE_FALSE_POSITIVE` | YES | 100% | 49.1 | 5522 |
| `ALT-STR-011` | STRUCTURING | `FILE_SAR` | `FILE_SAR` | YES | 100% | 51.6 | 5686 |
| `ALT-STR-012` | STRUCTURING | `FILE_SAR` | `FILE_SAR` | YES | 100% | 50.8 | 5686 |
| `ALT-SAN-001` | SANCTIONS_MATCH | `FILE_SAR` | `FILE_SAR` | YES | 100% | 51.7 | 5151 |
| `ALT-SAN-002` | SANCTIONS_MATCH | `ESCALATE_L2` | `ESCALATE_L2` | YES | 100% | 51.4 | 5139 |
| `ALT-SAN-003` | SANCTIONS_MATCH | `ESCALATE_L2` | `ESCALATE_L2` | YES | 100% | 52.4 | 5142 |
| `ALT-SAN-004` | SANCTIONS_MATCH | `FILE_SAR` | `FILE_SAR` | YES | 100% | 49.2 | 5151 |
| `ALT-SAN-005` | SANCTIONS_MATCH | `ESCALATE_L2` | `ESCALATE_L2` | YES | 100% | 52.1 | 5135 |
| `ALT-SAN-006` | SANCTIONS_MATCH | `REQUEST_RFI` | `REQUEST_RFI` | YES | 100% | 50.7 | 5157 |
| `ALT-SAN-007` | SANCTIONS_MATCH | `REQUEST_RFI` | `REQUEST_RFI` | YES | 100% | 49.1 | 5150 |
| `ALT-SAN-008` | SANCTIONS_MATCH | `REQUEST_RFI` | `REQUEST_RFI` | YES | 100% | 53.0 | 5170 |
| `ALT-SAN-009` | SANCTIONS_MATCH | `REQUEST_RFI` | `REQUEST_RFI` | YES | 100% | 53.1 | 5144 |
| `ALT-SAN-010` | SANCTIONS_MATCH | `CLOSE_FALSE_POSITIVE` | `CLOSE_FALSE_POSITIVE` | YES | 100% | 52.0 | 4989 |
| `ALT-SAN-011` | SANCTIONS_MATCH | `CLOSE_FALSE_POSITIVE` | `CLOSE_FALSE_POSITIVE` | YES | 100% | 60.5 | 4989 |
| `ALT-SAN-012` | SANCTIONS_MATCH | `CLOSE_FALSE_POSITIVE` | `CLOSE_FALSE_POSITIVE` | YES | 100% | 57.1 | 5000 |
| `ALT-HVT-001` | HIGH_VALUE_TRANSFER | `CLOSE_FALSE_POSITIVE` | `CLOSE_FALSE_POSITIVE` | YES | 100% | 54.1 | 5004 |
| `ALT-HVT-002` | HIGH_VALUE_TRANSFER | `CLOSE_FALSE_POSITIVE` | `CLOSE_FALSE_POSITIVE` | YES | 100% | 60.0 | 5006 |
| `ALT-HVT-003` | HIGH_VALUE_TRANSFER | `FILE_SAR` | `FILE_SAR` | YES | 100% | 55.9 | 4998 |
| `ALT-HVT-004` | HIGH_VALUE_TRANSFER | `CLOSE_FALSE_POSITIVE` | `CLOSE_FALSE_POSITIVE` | YES | 100% | 53.0 | 5004 |
| `ALT-HVT-005` | HIGH_VALUE_TRANSFER | `REQUEST_RFI` | `REQUEST_RFI` | YES | 100% | 56.1 | 4987 |
| `ALT-HVT-006` | HIGH_VALUE_TRANSFER | `REQUEST_RFI` | `REQUEST_RFI` | YES | 100% | 59.0 | 4992 |
| `ALT-HVT-007` | HIGH_VALUE_TRANSFER | `CLOSE_FALSE_POSITIVE` | `CLOSE_FALSE_POSITIVE` | YES | 100% | 57.3 | 5008 |
| `ALT-HVT-008` | HIGH_VALUE_TRANSFER | `FILE_SAR` | `FILE_SAR` | YES | 100% | 58.2 | 4996 |
| `ALT-HVT-009` | HIGH_VALUE_TRANSFER | `CLOSE_FALSE_POSITIVE` | `CLOSE_FALSE_POSITIVE` | YES | 100% | 52.3 | 4998 |
| `ALT-HVT-010` | HIGH_VALUE_TRANSFER | `REQUEST_RFI` | `REQUEST_RFI` | YES | 100% | 57.0 | 4991 |
| `ALT-HVT-011` | HIGH_VALUE_TRANSFER | `REQUEST_RFI` | `REQUEST_RFI` | YES | 100% | 54.0 | 4998 |
| `ALT-HVT-012` | HIGH_VALUE_TRANSFER | `FILE_SAR` | `FILE_SAR` | YES | 100% | 47.7 | 5001 |
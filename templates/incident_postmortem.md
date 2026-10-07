# SRE Incident Post-Mortem & Root Cause Analysis (RCA)

## Incident Overview
- **Incident ID:** {{incident_id}}
- **Severity Level:** {{severity_level}} (CRITICAL / HIGH / MEDIUM)
- **Affected Services / Components:** {{affected_components}}
- **Incident Commander / Lead SRE:** {{incident_lead}}
- **Duration / Outage Window:** {{start_time}} to {{end_time}} (Total Downtime: {{downtime_minutes}} mins)

---

## 1. Executive Summary
Brief non-technical description of the incident, customer impact, financial turnover affected, and resolution.

## 2. Customer & Business Impact
- Number of affected users / market participants: {{affected_users}}
- Failed transactions / trade volume stalled: {{failed_trades}}
- Service Level Agreement (SLA) breaches: {{sla_status}}

## 3. Incident Timeline (UTC / IST)
| Timestamp | Event / Telemetry Observed | Action Taken by SRE Team |
| :--- | :--- | :--- |
| `T - 00:00` | Initial alert trigger / spike in error rate | On-call engineer paged |
| `T + 00:05` | Triaged stack trace from remote server logs | Identified resource bottleneck |
| `T + 00:15` | Executed safe failover / service restart | System traffic recovered |
| `T + 00:25` | Health checks green across all cluster nodes | Incident resolved |

## 4. Technical Root Cause Analysis (RCA)
- **Primary Trigger:** Deep-dive explanation of the underlying failure mechanism (e.g. Connection Pool Exhaustion, Memory Leak, Network Partition, Unhandled NullPointer).
- **Contributing Factors:** Secondary factors that exacerbated the incident.

## 5. Corrective & Preventative Action Items (CAPA)
| Action Item | Type (Fix / Monitor / Architecture) | Owner | Target Completion Date |
| :--- | :--- | :--- | :--- |
| 1. Tune HikariCP connection pool settings | Bugfix | DevOps | Immediate |
| 2. Add automated health probe alerting | Monitoring | SRE Team | Sprint + 1 |
| 3. Stress test batch trader bidding load | Testing | QA Lead | Sprint + 2 |

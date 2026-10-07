# NeML Payment Gateway (NPG) & Clearing Engine Specification

## 1. System Architecture Overview
The NeML Payment Gateway (NPG) microservice (`PaymentGateWayService` running on `172.26.6.168:8080`) handles high-throughput financial transactions, fund routing, buyer escrow reconciliation, and real-time bank handshakes for electronic commodity trades.

### Architectural Components
1. **Core Java Spring Boot Microservice:** Containerized JVM runtime on JDK 17 with HikariCP database connection pooling (maximum 50 active connections per node).
2. **PostgreSQL Multi-AZ RDS Cluster (`umpremsl`):** Master-replica database cluster with read-replicas handling non-blocking trade inquiries.
3. **Banking Integration Layer:** Dual-redundant RESTful JSON and ISO 8583 integration with State Bank of India (SBI), HDFC Bank, ICICI Bank, and Axis Bank.
4. **Security & Cryptography:** AES-256-GCM payload encryption for all API bank handshakes and HMAC-SHA512 webhook signature verification.

---

## 2. API Endpoints & Financial Workflows

### Endpoint 1: Initiate Buyer Payment Order
- **Path:** `POST /api/v1/npg/orders/create`
- **Payload:**
  ```json
  {
    "tradeId": "TRD-2026-9081",
    "buyerId": "TRADER_KT1114",
    "grossAmount": 450000.00,
    "cessAmount": 6750.00,
    "userCharge": 900.00,
    "netPayable": 457650.00,
    "callbackUrl": "https://ump.neml.in/payment/callback"
  }
  ```
- **Response:** `200 OK` with PG redirection URL and dynamic Virtual Account Number (VAN).

### Endpoint 2: Bank Webhook & Auto-Reconciliation
- **Path:** `POST /api/v1/npg/webhooks/bank-notify`
- **SLA:** Must respond with HTTP 200 within 1500ms. If processing exceeds 3000ms, bank triggers exponential backoff retry.

---

## 3. SLA, Throughput & Performance Targets
- **Peak Transaction Throughput:** 1,200 financial transactions per minute during market closing hours (14:00 - 16:30 IST).
- **p99 End-to-End Latency:** Under 350ms for order creation and escrow status validation.
- **Availability Target:** 99.99% system availability with automated failover under 20 seconds.
- **Data Retention:** 10-year immutable audit log retention under banking compliance regulations.

---

## 4. Error Code Registry & Troubleshooting
- `ERR_NPG_001`: Insufficient Buyer EMD balance in escrow account.
- `ERR_NPG_002`: Bank gateway timeout (automated retry queued).
- `ERR_NPG_003`: Signature verification mismatch on incoming webhook.

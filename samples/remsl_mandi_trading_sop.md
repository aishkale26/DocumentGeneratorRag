# REMSL Unified Market Platform (UMP) Mandi Operations & Lot Lifecycle SOP

## 1. Overview of REMSL & Unified Market Platform (UMP)
Rashtriya e-Market Services Private Limited (REMSL) is a joint venture between the Government of Karnataka and National e-Markets Limited (NeML). REMSL manages the Unified Market Platform (UMP), an electronic commodity trading and auction platform connecting over 160 APMC mandis across Karnataka.

The primary mission of REMSL UMP is to provide transparent price discovery, automated assaying/quality grading, direct electronic bidding, online clearing and settlement, and Direct Benefit Transfer (DBT) to farmers.

---

## 2. Inbound Mandi Entry & Lot Creation Lifecycle
When a farmer arrives at an APMC mandi with agricultural produce (e.g. Maize, Cotton, Tur, Paddy, Groundnut):
1. **Gate Entry Registration:** The mandi gate operator registers the farmer using their 12-digit Aadhaar/FID number, vehicle registration number, commodity name, and estimated number of bags/weight.
2. **Lot ID Generation:** The UMP system automatically issues a unique 16-character alphanumeric Lot Identifier (e.g. `LOT-BLG-2026-8941`).
3. **Electronic Weighment:** Weighment is conducted on calibrated electronic weighbridges directly interfaced with the UMP system over RS-232 serial/TCP protocols, eliminating manual data entry tampering.
4. **Assaying & Quality Grading:** Certified assayers draw representative composite samples. The assaying module records moisture content, foreign matter percentage, damaged grains, and color grading. Assaying results are published on the electronic display screens and the trader mobile application before bidding opens.

---

## 3. Unified Auction & Bidding Mechanisms
REMSL UMP supports four distinct electronic price discovery modes:
1. **English Auction (Ascending Clock):** Bidders submit progressively higher bids above a reserve price within a 15-minute active trading window. If a bid is placed in the last 2 minutes, the window auto-extends by 120 seconds.
2. **Closed Tender (Blind Bidding):** Traders enter sealed bids by 13:00 IST. The UMP matching engine computes the Highest Bidder (H1) at 13:30 IST.
3. **Dutch Auction (Descending Clock):** The auctioneer starts at a premium ceiling price and decrements the price until the first trader accepts.
4. **MSP Procurement Mode:** Government procurement agencies purchase produce at notified Minimum Support Prices when market rates fall below statutory benchmarks.

---

## 4. Post-Trade Clearing, Settlement & Escrow Accounting
Once the farmer accepts the H1 bid:
1. **Trade Confirmation Slip (Form 8):** Electronically generated with H1 trader details, gross weight, net rate per quintal, and total lot value.
2. **NeML Payment Gateway (NPG) Invoicing:** The buyer must deposit 100% of the lot value into the REMSL designated Escrow Account within T+1 banking days.
3. **Automated Deductions:**
   - APMC Market Cess: 1.5% of gross trade value deducted and routed to the respective APMC account.
   - User Charges: 0.2% routed to REMSL operational fund.
4. **Direct Benefit Transfer (DBT):** The net sale proceeds are credited directly into the farmer's verified bank account via NPCI/NEFT within 2 hours of payment clearance.
5. **Electronic Gate Pass (e-Permit):** Upon settlement confirmation, the system issues a tamper-proof QR-coded e-Permit authorizing the buyer's vehicle to exit the mandi premises.

---

## 5. Dispute Resolution & Default Protocols
- If a buyer fails to fund the escrow account within the T+1 deadline, a statutory penalty of 0.5% per day is levied, and their Earnest Money Deposit (EMD) is frozen.
- If quality discrepancy exceeds 5% of assaying parameters, the lot is referred to the Mandi Arbitration Committee.

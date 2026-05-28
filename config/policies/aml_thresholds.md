# Anti-Money Laundering Thresholds

## CTR Filing Requirement
Cash transactions or wire transfers exceeding $10,000 in a single day must be reported via Currency Transaction Report (CTR) to FinCEN within 15 days of the transaction date. This applies to both individual transactions and aggregated transactions from the same customer on the same business day.

## Structuring Detection
Multiple transactions structured to avoid the $10,000 reporting threshold within a 48-hour window constitute potential structuring and must be flagged for review. Structuring is a federal crime under 31 U.S.C. § 5324. Indicators include:
- Two or more transactions totalling just below $10,000 within 48 hours
- Transactions of $9,000–$9,999 with no apparent business justification
- Split deposits across multiple branches or accounts on the same day

## Suspicious Activity Reports (SAR)
A SAR must be filed within 30 days when a transaction involves $5,000 or more and the institution knows, suspects, or has reason to suspect the transaction involves funds from illegal activity, is designed to evade reporting requirements, or lacks a lawful purpose.

## Aggregate Monitoring
Cumulative transactions from a single account exceeding $25,000 in a 7-day rolling window trigger enhanced monitoring. Compliance must be notified for accounts whose 30-day aggregate exceeds $100,000 if the account risk score is above 0.6.

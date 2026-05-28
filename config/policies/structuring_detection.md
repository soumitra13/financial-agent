# Structuring Detection Policy

## Definition
Structuring (also called "smurfing") is the practice of breaking up large financial transactions into smaller ones to avoid triggering currency reporting requirements. It is a federal crime under 31 U.S.C. § 5324 regardless of whether the underlying funds are from legitimate sources.

## Detection Rules

### Round-Number Threshold Proximity
Transactions at or between $9,000 and $9,999 are flagged for potential structuring review. Round-number amounts ($9,000, $9,500, $9,900) carry higher suspicion than irregular amounts.

### 48-Hour Aggregation Window
If two or more transactions from the same account sum to more than $10,000 within a 48-hour window, and no single transaction exceeded $10,000, the pattern must be flagged as potential structuring.

### Multiple Account Structuring
Transactions across multiple accounts controlled by the same beneficial owner that collectively exceed $10,000 within 24 hours must be treated as a single transaction for reporting purposes.

### Repetitive Pattern Detection
If an account shows a recurring pattern of sub-threshold transactions (e.g., $9,500 every Monday for 4+ weeks), this constitutes a structuring pattern even if individual transactions don't trigger review.

## Required Actions
- Flag all transactions involved in the pattern
- Freeze new transactions pending review if the pattern repeats more than 3 times
- File SAR within 30 days if structuring is confirmed
- Document the full transaction chain in the audit log

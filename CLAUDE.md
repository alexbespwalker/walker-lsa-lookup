# LSA Lead Lookup

Internal tool for Walker Advertising to look up LSA (Local Services Ads) leads by phone number and determine rating/pricing/disposition.

## Architecture

```
index-v5.html  →  POST to n8n webhook  →  MS SQL (Waycool/WacatsNew)  →  Rating Logic  →  HTML response
```

- **Frontend**: Static HTML form (`index-v5.html`), hosted on GitHub Pages or served locally
- **Backend**: n8n workflows on `automation.walkeradvertising.com:5678`
- **Database**: Microsoft SQL Server (Waycool/WacatsNew) via n8n credential
- **Rating Logic**: Flat lookup table generated from Excel source of truth (710 rules, 720 entries with aliases)

## Key Files

| File | Purpose |
|------|---------|
| `index-v5.html` | Current frontend form (Excel-driven rules, points to `/webhook/lsa-lookup-final`) |
| `scripts/generate_rules.py` | Excel → JSON/JS converter |
| `scripts/requirements.txt` | Python dependencies (openpyxl) |
| `rules/rules.json` | Generated lookup table (720 entries) |
| `rules/rules_n8n_snippet.js` | Ready-to-paste JS for n8n Code node |
| `Copy of LSA_Updated_Signal.xlsx` | Excel source of truth (710 rules) |
| `workflows/lsa-lead-lookup-v5.json` (local) / `workflows/lsa-lookup-v5.json` (GitHub) | n8n v5 workflow export |
| `workflows/lsa-lookup-vfinal-backup.json` | n8n v4/vFinal workflow export |

## Commands

```bash
# Generate rules from Excel (run from project root)
python3 scripts/generate_rules.py

# Output:
#   rules/rules.json
#   rules/rules_n8n_snippet.js
```

---

## Active Workflows

Both workflows are currently **ACTIVE** pending QA validation.

### v4 / vFinal (Production)

| Field | Value |
|-------|-------|
| Workflow ID | `IAtDWIqffTyp5RWw` |
| Name | LSA Lead Lookup vFinal (Webhook) |
| Webhook path | `/webhook/lsa-lookup-final` (production) |
| Status | **ACTIVE** |
| Rating logic | broadId-based (hardcoded in Code node) |
| Date filter | YES (7-day) |
| Response time | ~0.28s |
| Credential | Microsoft SQL WacatsNew - Alex B (`Xk0Pjz0ws9gsFuvb`) |

### v5 (Test / Staging)

| Field | Value |
|-------|-------|
| Workflow ID | `1bmHd4w0xOovtyLn` |
| Name | LSA Lead Lookup v5 |
| Webhook path | `/webhook/lsa-lookup-v5-test` (test) |
| Status | **ACTIVE** |
| Rating logic | Excel-driven flat lookup (710 rules from `generate_rules.py`) |
| Date filter | YES (7-day) |
| Response time | ~0.34s |
| Credential | Microsoft SQL WacatsNew - Alex B (`Xk0Pjz0ws9gsFuvb`) |

### Workflow Nodes (both v4 and v5)

1. Webhook Trigger (POST, CORS enabled)
2. Validate & Clean (phone normalization, auth check)
3. Auth OK? (IF node)
4. Query Waycool (MS SQL query)
5. Rating Logic (v4: broadId-based / v5: Excel flat lookup)
6. Respond Success (HTML template)
7. Respond Denied (error page)

---

## 7-Day Date Filter

**What it does**: Limits the SQL scan to calls from the last 7 days, reducing the row count from the full table (millions of rows) to a manageable window.

**Where it is**: The `Query Waycool` Microsoft SQL node in both workflows.

**SQL before**:
```sql
WHERE {{ $json.whereClause }}
ORDER BY c.StartTime DESC
```

**SQL after**:
```sql
-- DATE FILTER: limits scan to last 7 days. To revert, remove the AND line and the parentheses around whereClause
WHERE ({{ $json.whereClause }})
  AND c.StartTime >= DATEADD(day, -7, GETDATE())
ORDER BY c.StartTime DESC
```

**How to revert**: Remove the `AND c.StartTime >= DATEADD(day, -7, GETDATE())` line and change `({{ $json.whereClause }})` back to `{{ $json.whereClause }}` (remove the parentheses).

**Edge cases**: `c.StartTime` is when the call happened, not when the record was created. A new call from a 3-year-old contact still gets a recent `StartTime` and will be captured within the 7-day window.

---

## SQL REPLACE Chain

The SQL WHERE clause uses triple-nested `REPLACE()` to strip formatting characters:

```sql
REPLACE(REPLACE(REPLACE(c.PrimaryPhoneNum, '-', ''), '(', ''), ')', '') LIKE '%6192486640%'
```

**Why we keep it**: The DB stores formatted numbers (e.g., `619-248-6640`). Without REPLACE, the pattern `LIKE '%6192486640%'` requires contiguous digits but dashes interrupt the match. A multi-wildcard approach (`LIKE '%619%248%6640%'`) would be slower due to backtracking and could false-match.

**Not the bottleneck**: Per-row REPLACE cost is negligible (microseconds). The real bottleneck was row count — any `LIKE '%...%'` (leading wildcard) forces a full table scan. The date filter is what fixed performance.

**Known gap**: REPLACE only strips `-`, `(`, `)` — not spaces. If the DB stored `(619) 248-6640` (with a space), matching would fail. This works in production because Waycool stores numbers with dashes/parens but no spaces.

---

## Excel → JSON Pipeline

1. Update the Excel file (`Copy of LSA_Updated_Signal.xlsx`)
2. Run `python3 scripts/generate_rules.py`
3. Copy content of `rules/rules_n8n_snippet.js` into the Rating Logic node in n8n
4. Or use n8n API to update the node programmatically

The script reads the "General Settings" sheet, maps Excel values to LSA platform values (rating text, job types, prices), generates no-space aliases for codes with spaces (e.g., `LEQ - SH` → `LEQ-SH`), and outputs both JSON and JS formats.

---

## Bugs Found & Fixed (v5 Development)

### 1. Spam Display Fields

**Problem**: When spam was detected via notes keywords (e.g., "hung up"), the lookup returned `DEFAULT_RULE` fields — Law Type showed "Unknown" instead of the real code's value (e.g., "Call Back").

**Fix**: Changed spam detection to look up the Excel rule first, then overlay spam fields (`mark_as`, `rating`, `reason`) on top of the real rule instead of on top of DEFAULT_RULE.

### 2. Textarea ID with Space (n8n Expression Quirk)

**Problem**: Rendered HTML had `<textarea id="txt 0">` (with a space) but the copy button called `getElementById('txt0')` (no space). Copy button silently failed.

**Root cause**: n8n's expression engine inserted whitespace when rendering `id="txt${idx}"` inside a `.map()` callback.

**Fix**: Changed to `id="${'txt'+idx}"` which forces JS string concatenation within a single expression, preventing n8n from inserting whitespace.

### 3. CSS Class Verification

Card-header CSS classes (`booked`, `archive`, `notfound`, `live`) were verified working correctly. The `live` class with yellow gradient styling applies correctly when `is_live_call` is true.

---

## Performance

### Before Date Filter

```
Min: 3.6s  Max: 60.2s  Avg: 13.2s
Under 10s: 11/15 executions
Over 20s:  3/15 executions
Over 40s:  2/15 executions
```

99.9% of execution time was in the `Query Waycool` node (SQL query). All other nodes combined: <50ms.

### Cold-Connection Spike Test

Sent 3 requests to vFinal, 30 seconds apart:

| Request | After Idle | Server Duration | HTTP Status |
|---------|-----------|-----------------|-------------|
| 1 (cold) | Minutes idle | **13.0s** | 200 |
| 2 (warm) | 0s | **3.9s** | 200 |
| 3 (cold again) | 30s idle | **60.1s** | 504 (gateway timeout at 20s, n8n completed at 60s) |

The spike does NOT self-resolve. Even 30s of idle causes the connection to go cold. The Azure Application Gateway cuts off at ~20s.

### After Date Filter

- **v5**: 0.34 seconds
- **vFinal**: 0.28 seconds

**Summary**: 13-60s → 0.3s by adding `AND c.StartTime >= DATEADD(day, -7, GETDATE())`.

---

## Learnings for Future

### Date Filters on Large Tables
Leading-wildcard LIKE queries (`LIKE '%...'`) force full table scans regardless of indexes. On multi-million-row tables, always add a date filter to limit scan scope. The date filter reduced query time from 13-60s to 0.3s.

### n8n API Pattern
When creating/updating workflows via the n8n API, webhook nodes require a `webhookId` field to register the webhook path. Without it, the webhook returns 404 "not registered" even when `active: true` is set. This is undocumented.

### n8n Expression Quirks
- Template literals like `id="txt${idx}"` can insert unexpected whitespace when rendered by n8n's expression engine. Workaround: use `id="${'txt'+idx}"` to force string concatenation within a single expression.
- The same variable (`idx`) can produce different whitespace behavior depending on surrounding string context in the same `.map()` callback.

### Connection Pooling
MS SQL connections through n8n go cold after ~30s of idle. This is a platform-level issue, not fixable in workflow logic. The correct fix is reducing query time so that even cold connections complete within the gateway timeout (20s).

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1-v3 | Pre-2026 | Initial implementations |
| v4/vFinal | 2026-01 | Copy fix, media source tracking, live call detection, broadId-based rating |
| v5 | 2026-02-05 | Excel-driven flat lookup (710 rules), 7-day date filter, spam display fix, textarea ID fix |

## Current Status

Both v4 (vFinal) and v5 are **ACTIVE** simultaneously:
- **vFinal** serves production on `/webhook/lsa-lookup-final` (the path `index-v5.html` points to)
- **v5** serves test on `/webhook/lsa-lookup-v5-test` for parallel QA validation
- Once v5 QA is complete, v5 can be switched to the production path and vFinal deactivated

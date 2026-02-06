# LSA Lead Lookup

Internal tool for Walker Advertising to look up LSA (Local Services Ads) leads by phone number and determine rating/pricing/disposition.

## Architecture

```
index-v5.html  →  n8n webhook (POST)  →  MS SQL (Waycool DB)  →  Rating Logic  →  HTML response
```

- **Frontend**: Static HTML form (hosted on GitHub Pages or served locally)
- **Backend**: n8n workflow on `automation.walkeradvertising.com:5678`
- **Database**: Microsoft SQL Server (Waycool/WacatsNew) via n8n credential
- **Rating Logic**: Flat lookup table generated from Excel source of truth

## Key Files

| File | Purpose |
|------|---------|
| `index-v5.html` | Frontend form (v5 - Excel-driven rules) |
| `scripts/generate_rules.py` | Excel → JSON/JS converter |
| `scripts/requirements.txt` | Python dependencies (openpyxl) |
| `rules/rules.json` | Generated lookup table (720 entries) |
| `rules/rules_n8n_snippet.js` | Ready-to-paste JS for n8n Code node |
| `Copy of LSA_Updated_Signal.xlsx` | Excel source of truth (710 rules) |
| `workflows/lsa-lookup-v5.json` | n8n v5 workflow export |
| `workflows/lsa-lookup-vfinal-backup.json` | Previous vFinal workflow backup |

## Commands

```bash
# Generate rules from Excel (run from project root)
python3 scripts/generate_rules.py

# Output:
#   rules/rules.json
#   rules/rules_n8n_snippet.js
```

## n8n Workflow

- **Workflow ID**: `1bmHd4w0xOovtyLn` (v5)
- **Webhook path**: `/webhook/lsa-lookup-v5-test` (test) → `/webhook/lsa-lookup-final` (production)
- **Credential**: `Microsoft SQL WacatsNew - Alex B` (ID: `Xk0Pjz0ws9gsFuvb`)

### Nodes
1. Webhook Trigger (POST, CORS enabled)
2. Validate & Clean (phone normalization, auth check)
3. Auth OK? (IF node)
4. Query Waycool (MS SQL query)
5. Rating Logic (flat lookup from Excel-generated rules)
6. Respond Success (HTML template)
7. Respond Denied (error page)

## Rating Logic (v5)

v5 replaces v4's broadId-based logic with a flat code-level lookup table:
- 710 rules from Excel, keyed by uppercase call type code
- 10 no-space aliases (e.g., `LEQ-SH` for `LEQ - SH`)
- Spam detection via notes keywords (overrides Excel rules)
- Unknown codes default to ARCHIVE

### How to update rules
1. Update the Excel file (`Copy of LSA_Updated_Signal.xlsx`)
2. Run `python3 scripts/generate_rules.py`
3. Copy content of `rules/rules_n8n_snippet.js` into the Rating Logic node in n8n
4. Or use n8n API to update the node programmatically

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1-v3 | Pre-2026 | Initial implementations |
| v4 | 2026-01 | Copy fix, media source tracking, live call detection |
| v5 | 2026-02 | Excel-driven flat lookup (710 rules), replaces broadId logic |

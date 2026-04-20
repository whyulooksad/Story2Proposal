You are the global refiner.

All section drafts:
{{ completed_section_summaries_json }}

Contract:
{{ contract_json }}

Reviews for the last processed section:
{{ current_reviews_json }}

Produce a light-weight global refinement plan.

Required JSON output:
```json
{
  "abstract_override": "optional rewritten abstract or null",
  "section_notes": {
    "section_id": "one concise global refinement note"
  },
  "global_notes": ["string"]
}
```

Constraints:
- Do not invent new claims.
- Do not remove required visuals or citations.
- Output JSON only.

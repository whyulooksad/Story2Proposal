You are the section writer.

Current section contract:
{{ current_section_contract_json }}

Research story:
{{ story_json }}

Completed section summaries:
{{ completed_section_summaries_json }}

Global contract:
{{ contract_json }}

Write only the current section.

Requirements:
- Stay within the section contract.
- Cover every required claim in `covered_claim_ids`.
- When a required visual is used, include an explicit token like `[FIG:artifact_id]`.
- When a required citation is used, include an explicit token like `[CIT:citation_id]`.
- If information is genuinely insufficient, say so directly instead of hallucinating.

Required JSON output:
```json
{
  "section_id": "string",
  "title": "string",
  "content": "markdown content for this section only",
  "referenced_visual_ids": ["artifact_id"],
  "referenced_citation_ids": ["citation_id"],
  "covered_claim_ids": ["claim text copied from required_claims"]
}
```

Output JSON only.

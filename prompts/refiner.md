You are the global refiner.

All section drafts:
{{ completed_section_summaries_json }}

Structured section draft state:
{{ completed_section_drafts_json }}

Contract:
{{ contract_json }}

Reviews for the last processed section:
{{ current_reviews_json }}

Language requirement:
{{ writing_language_instruction }}

Produce a global rewrite result.

Required JSON output:
```json
{
  "abstract_override": "optional rewritten abstract or null",
  "rewrite_goals": ["string"],
  "section_rewrites": [
    {
      "section_id": "string",
      "title": "string",
      "rewritten_content": "full rewritten section body",
      "rationale": "string",
      "preserved_claim_ids": ["claim_id"],
      "preserved_visual_ids": ["artifact_id"],
      "preserved_citation_ids": ["citation_id"]
    }
  ],
  "terminology_updates": {
    "old_term": "preferred_term"
  },
  "contract_patches": [
    {
      "patch_type": "append_glossary|update_visual_placement|require_visual_explanation|tighten_validation_rule|register_revision_note",
      "target_id": "string",
      "value": {}
    }
  ]
}
```

Constraints:
- Do not invent new claims, evidence, visuals, or citations.
- You may rewrite whole sections in this stage if global coherence requires it.
- Every rewritten section must preserve the section's required claims, citations, and visuals from the contract.
- Use `section_rewrites` only when you can provide a full replacement body that is better globally aligned than the current draft.
- Use `rewrite_goals` to explain the whole-paper consolidation strategy.
- Harmonize terminology across sections.
- Use `contract_patches` when global refinement should strengthen the contract itself.
- Keep all paper-facing text in the required output language.
- Output JSON only.

export type EvaluationCriterionPayload = {
  criterion_id: string;
  label: string;
  passed: boolean;
  evidence?: string[];
};

export type EvaluationPayload = {
  protocol_version?: string;
  overall_score?: number;
  strengths?: string[];
  risks?: string[];
  recommended_actions?: string[];
  dimensions?: Array<{
    name: string;
    score: number;
    passed: boolean;
    criteria?: EvaluationCriterionPayload[];
    evidence?: string[];
  }>;
};

export type BenchmarkPayload = {
  protocol_version?: string;
  benchmark_name?: string;
  primary_candidate_id?: string;
  winner_candidate_id?: string;
  summary?: string[];
  candidates?: Array<{
    candidate_id: string;
    label: string;
    source: string;
    report: {
      overall_score: number;
    };
  }>;
  comparisons?: Array<{
    candidate_id: string;
    baseline_id: string;
    overall_delta: number;
    summary?: string[];
    dimension_deltas?: Array<{
      name: string;
      delta: number;
    }>;
  }>;
};

export type ContractPayload = {
  paper_title?: string | null;
  version?: number;
  target_venue?: string | null;
  style_guide?: {
    output_language?: string;
    tone?: string;
    citation_style?: string;
  };
  global_status?: {
    state?: string;
    current_section_id?: string | null;
    completed_sections?: string[];
    pending_sections?: string[];
    warnings?: string[];
  };
  sections?: Array<{
    section_id: string;
    title: string;
    purpose?: string;
    status?: string;
    required_claim_ids?: string[];
    required_evidence_ids?: string[];
    required_visual_ids?: string[];
    required_citation_ids?: string[];
    source_story_fields?: string[];
    depends_on_sections?: string[];
  }>;
  visuals?: Array<{
    artifact_id: string;
    label?: string;
    kind?: string;
    semantic_role?: string;
    placement_constraint?: string;
    render_status?: string;
    target_sections?: string[];
  }>;
  citations?: Array<{
    citation_id: string;
    citation_key?: string;
    title?: string;
    status?: string;
    required_sections?: string[];
    grounded_claim_ids?: string[];
  }>;
  validation_rules?: Array<{
    rule_id: string;
    rule_type?: string;
    description?: string;
    severity?: string;
    scope?: string;
    target_id?: string | null;
  }>;
  revision_log?: Array<{
    revision_id: string;
    stage?: string;
    agent?: string;
    summary?: string;
    affected_sections?: string[];
    patch_types?: string[];
  }>;
};

export const dimensionLabels: Record<string, string> = {
  structural_integrity: "结构完整性",
  writing_clarity: "写作清晰度",
  methodological_rigor: "方法严谨性",
  experimental_substance: "实验实质性",
  citation_hygiene: "引用卫生",
  reproducibility: "可复现性",
  formatting_stability: "格式稳定性",
  visual_communication: "视觉表达",
};

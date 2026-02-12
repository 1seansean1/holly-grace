"""Informational Monism (IM) tool chain.

Implements the 9-tool pipeline from the IM paper's Architecture Selection Rule:
  1. im_parse_goal_tuple        — G⁰ → candidate G¹ tuple
  2. im_generate_failure_predicates — G¹ → {f₁,…,fₘ} + blocks + coupling axes
  3. im_build_coupling_model    — predicates → M = Cov_ν(g), PSD projection
  4. im_estimate_codimension    — M → eigenspectrum, cod_π(G) = rank_τ(M)
  5. im_rank_budget_and_regime  — agent pool → rank budget, regime classification
  6. im_memory_tier_design      — codimension + regime → tier structure, crystallisation
  7. im_synthesize_agent_specs  — M + agents → optimal assignment α*, J_α, Δ
  8. im_synthesize_workflow_spec — assignment → topology, channels, compiled graph
  9. im_validate_feasibility    — Thm. architecture-design: Δ=0 or remediation
"""

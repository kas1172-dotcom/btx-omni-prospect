export type RelationshipMode = 'commercial_fit' | 'cross_account_experience' | 'contact_candidates' | 'documented_access'
export type OmniRelationshipSelection = { source_account_id: string; target_ids: string[]; mode: RelationshipMode; as_of: string; depth: number; path_id: string; graph_revision: string; source_component_id?: string; target_component_id?: string }
export type CanonicalGraphNode = { id: string; canonical_id: string; kind: string; label: string; account_id?: string }
export type CanonicalGraphEdge = { id: string; source: string; target: string; predicate: string; evidence_ids: string[]; truth_class: string; observed_on?: string; lineage_groups: string[]; source_lineage: string[]; account_id?: string; path_ids?: string[]; expansion_owners?: string[] }
export type RankedRoute = {
  path_id: string; node_ids: string[]; edge_ids: string[]; inverse_steps: boolean[]; hop_count: number
  steps: CanonicalGraphNode[]; utility: string; execution_status: string; next_action: string
  assertions?: Array<{ id: string; predicate: string; inverse: boolean; truth_class: string }>
  factors: { bottleneck: number; relevance: number; evidence: number; freshness: number; coverage: string }
  factor_reasons: Array<{ edge_id: string; B: number; E: number; F: number; reason: string; truth_class: string }>
  constraints: Array<{ id: string; reason: string; evidence_ids: string[] }>; evidence_ids: string[]
  component_context: Array<{ id: string; label: string; account_id: string; facility_id?: string; business_unit_id: string }>
}
export type RelationshipQuery = { source_account_id: string; mode: RelationshipMode; depth: number; source_component_id?: string; target_component_id?: string; target_account_id?: string; selected_path_id?: string; node_budget: number; edge_budget: number; expanded_node_ids?: string[]; context_page?: number; expected_graph_revision?: string; include_record_context?: boolean }
export type RankedRelationships = {
  mode: RelationshipMode; groups: Record<string, { routes: RankedRoute[] }>; evaluated_routes?: RankedRoute[]; research_candidates: RankedRoute[]
  candidate_count: number; additional_route_count?: number; search_complete: boolean; searched_depth: number; examined_count: number; stop_reason?: string
  eligible_graph_revision?: string; rubric_version?: string; commercial_as_of?: string[]; reason?: string
  temporal_limits?: Record<string, { undated_plans_excluded_from_historical_query: number; plan_date_policy: string }>
  scope?: { source_id: string; target_ids: string[]; as_of: string; source_component_id?: string; target_component_id?: string }
  graph: { nodes: CanonicalGraphNode[]; edges: CanonicalGraphEdge[]; selected_path_id?: string; additional_route_nodes?: number; neighborhood_depth?: number; expanded_node_ids?: string[]; context_page?: number; page_count?: number; context_edge_count?: number; hidden_context_edges?: number; context_complete?: boolean; context_stop_reason?: string; selection_elapsed_ms?: number }
  query_options?: { components: Array<{ id: string; label: string }>; target_components: Array<{ id: string; label: string }>; accounts: Array<{ id: string; label: string }> }
  related_intelligence?: Array<{ event_id: string; account_id: string; assessment: { headline: string; why_it_may_matter: string; recommended_action?: string; commercial_relevance_state?: string; priority_eligible?: boolean; assessment_id?: string; assessment_version?: number } }>
  intelligence_boundary?: string
}

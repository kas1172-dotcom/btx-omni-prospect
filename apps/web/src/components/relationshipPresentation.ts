const predicateLabels: Record<string, string> = {
  PUBLISHED_ROLE_AT: 'Recorded role affiliation', EMPLOYED_BY: 'Recorded role affiliation', WORKS_AT: 'Recorded role affiliation',
  INTRODUCED_TO: 'Recorded introduction', DOCUMENTED_ACCESS: 'Recorded access',
  QUOTED_TO: 'Historical quoting experience', ORDERED_FROM: 'Historical commercial experience', SUPPLIED_TO: 'Historical supply experience',
  CAPABILITY_MATCH: 'Capability alignment', CAPABILITY_FIT: 'Capability alignment', SHARED_PROGRAM: 'Shared program experience',
  OWNS_PROGRAM: 'Program ownership context', PARTICIPATES_IN: 'Recorded participation',
}

export function relationshipPredicateLabel(value?: string) {
  if (!value) return 'Relationship evidence'
  return predicateLabels[value.toUpperCase()] ?? 'Recorded relationship'
}

export function relationshipEvidenceLabel(value?: string) {
  const state = value?.toUpperCase()
  if (state === 'CONFIRMED' || state === 'VERIFIED' || state === 'VALIDATED') return 'Recorded relationship'
  if (state === 'INFERRED' || state === 'HYPOTHESIS') return 'Possible route to investigate'
  if (state === 'MISSING' || state === 'CONFLICTING' || state === 'UNUSABLE') return 'Not currently actionable'
  return state === 'NEEDS_VALIDATION' || state === 'NEEDS_CHECK' ? 'Needs validation' : 'Evidence needs review'
}

export function relationshipRouteStatus(value?: string) {
  const state = value?.toLowerCase().replaceAll(' ', '_')
  if (state === 'validated' || state === 'recommended' || state === 'supported') return 'Recorded relationship'
  if (state === 'blocked' || state === 'unusable' || state === 'not_actionable') return 'Not currently actionable'
  return 'Needs validation'
}

export const relationshipDirectionLabel = (inverse?: boolean) => inverse ? 'Explored in reverse; original assertion direction retained' : 'Recorded assertion direction'

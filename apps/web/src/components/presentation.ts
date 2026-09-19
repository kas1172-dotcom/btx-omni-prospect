import type { Principal } from '../types/api'

export type PresentationDomain = 'general' | 'workflow' | 'assessment' | 'evidence' | 'federal' | 'relationship' | 'communication' | 'provider'

const labels: Record<string, string> = {
  ACCOUNT: 'Organization', BUSINESS_UNIT: 'Business unit', FACILITY: 'Facility', BTX_FACILITY: 'BTX facility', ACCOUNT_FACILITY: 'Organization facility', PERSON: 'Person', ROLE: 'Role', ROLE_TARGET: 'Role to research', PROGRAM: 'Program', COMPONENT: 'Component', COMPONENT_CLASS: 'Component family', CAPABILITY: 'Capability', CERTIFICATION: 'Certification', PUBLIC_EVENT: 'Public development', OPPORTUNITY: 'Opportunity',
  QUOTED: 'Quoted', QUALIFIED: 'Qualified', NEGOTIATION: 'In negotiation', PROPOSAL_APPROVED: 'Proposal approved', QUALIFY: 'Qualification', ACTIVE: 'Active', CLOSED: 'Closed',
  CROSS_BU_COORDINATION: 'Coordinate business units', OVERDUE_ORDER: 'Delivery commitment needs review', QUOTE_FOLLOW_UP: 'Follow up on the quote', STALE_QUOTE: 'Confirm the quote is still active',
  ALL: 'All', AVAILABLE: 'Available', UNAVAILABLE: 'Unavailable', CONNECTED: 'Connected', CONFIGURED: 'Configured', NOT_CONFIGURED: 'Not configured', ADMIN_MANAGED: 'Managed by an administrator', RESTRICTED: 'Restricted',
  OPEN: 'Open', IN_PROGRESS: 'In progress', COMPLETED: 'Completed', CANCELED: 'Canceled', DRAFT: 'Draft', READY: 'Ready for delivery confirmation', SENT: 'Sent', PENDING: 'Awaiting review', APPROVED: 'Approved by reviewer', REJECTED: 'Not approved', NOT_REQUIRED: 'No approval required',
  HIGH: 'High', MEDIUM: 'Medium', LOW: 'Low', INFORMATIONAL: 'Informational',
  PENDING_ANALYSIS: 'Analysis in progress', INCOMPLETE: 'Analysis incomplete', UNASSESSED: 'Not yet assessed', REVIEW_REQUIRED: 'Needs validation', ESTABLISHED_ACCOUNT_REVIEW: 'Account review supported', ESTABLISHED_COMMERCIAL_RELEVANCE: 'Commercial relevance established',
  RESOLVED_ELIGIBLE: 'Evidence resolved for review', RESOLVED_NEEDS_REVIEW: 'Evidence needs review', RESOLVED: 'Resolved', UNRESOLVED: 'Unresolved', WITHHELD: 'Withheld from seller use',
  CONFIRMED: 'Confirmed evidence', CITED: 'Cited source', PUBLICLY_VERIFIED: 'Public identity verified', RESEARCHED_PUBLIC: 'Public research reviewed', REFERENCE_SOURCE: 'Reference source', BROWSER_VERIFIED: 'Source opened and reviewed', CURATED_PUBLIC: 'Saved public evidence', CURATED_POC_PUBLIC: 'Saved public source', LIVE_PUBLIC: 'Collected public evidence', SAMPLE: 'Controlled commercial records', INTERNAL_COMMERCIAL: 'Internal commercial record',
  DIRECT_BTX: 'Direct BTX pursuit', CUSTOMER_EXPANSION: 'Customer expansion', STRATEGIC_PARTNER: 'Strategic partnership', NEW_PROSPECT: 'New prospect development', CAPABILITY_INVESTMENT: 'Capability investment', MARKET_WATCH: 'Market watch',
  SOURCES_SOUGHT: 'Sources Sought', PRE_SOLICITATION: 'Pre-solicitation', SOLICITATION: 'Open solicitation', SPECIAL_NOTICE: 'Special notice', AWARD: 'Awarded', MODIFICATION: 'Modified notice', CANCELLED: 'Cancelled', INACTIVE: 'Inactive', ARCHIVED: 'Archived',
  RECORDED: 'Recorded relationship', INFERRED: 'Evidence-backed inference', HYPOTHETICAL: 'Research hypothesis', NEEDS_RESEARCH: 'Needs research', CONFLICTING: 'Conflicting evidence',
  CURRENT: 'Current', STALE: 'May be outdated', PUBLICATION_DATE_UNAVAILABLE: 'Publication date unavailable', UPCOMING: 'Upcoming', OBSERVED: 'Observed', UNKNOWN: 'Unknown',
  CUSTOMER: 'Customer', PROSPECT: 'Prospect', UNCLASSIFIED: 'Classification unavailable',
  EMAIL: 'Email', PHONE: 'Phone', MEETING: 'Meeting', NOTE: 'Note',
  CONTRACT_AWARD: 'Contract award', CONTRACT_MODIFICATION: 'Contract modification', SUPPLIER_AWARD: 'Supplier award', FACILITY_EXPANSION: 'Facility expansion', CAPACITY_EXPANSION: 'Capacity expansion', NEW_FACILITY: 'New facility', PRODUCTION_RAMP: 'Production ramp', PRODUCTION_DELAY: 'Production delay', BACKLOG_CHANGE: 'Backlog change', PROGRAM_LAUNCH: 'Program launch', PRODUCT_LAUNCH: 'Product launch', GOVERNMENT_FUNDING: 'Government funding', CAPITAL_INVESTMENT: 'Capital investment', PARTNERSHIP: 'Partnership', M_AND_A: 'Merger or acquisition', REGULATORY_APPROVAL: 'Regulatory decision', REGULATORY_CHANGE: 'Regulatory change', FACILITY_CLOSURE: 'Facility closure', WORKFORCE_REDUCTION: 'Workforce reduction', SUPPLY_CHAIN_CHANGE: 'Supply-chain change',
  ACCOUNT_PROGRAM: 'participates in program', PROGRAM_COMPONENT: 'includes component', ACCOUNT_COMPONENT: 'has component context', FACILITY_BU: 'operates within business unit', PRODUCED_ACCEPTED_COMPONENT: 'produced accepted component', SCENARIO_SUPPLIER_FOR_COMPONENT: 'scenario supplier for component', CAPABILITY_FIT: 'capability fit', PUBLISHED_ROLE: 'published role', QUALIFICATION: 'qualification evidence', PRODUCT_PLATFORM: 'product-platform association',
}

const identifierPattern = /^(?:[A-Z]{2,}\d*[-_:]|[a-z]+-\d+$|[0-9a-f]{8}-[0-9a-f-]{27,}$)/i
const enumPattern = /^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$/

export function presentationLabel(value: string | null | undefined, domain: PresentationDomain = 'general'): string {
  void domain
  if (!value) return 'Unavailable'
  const normalized = value.trim().toUpperCase().replaceAll(' ', '_')
  if (labels[normalized]) return labels[normalized]
  if (!enumPattern.test(value) && !identifierPattern.test(value)) return value
  return 'Status available in supporting details'
}

export function actorDisplayName(actorId: string | null | undefined, principal?: Principal): string {
  if (!actorId) return 'Unassigned'
  if (principal?.user_id === actorId && principal.display_name) return principal.display_name
  if (/manager|approver/i.test(actorId)) return 'Approving manager'
  if (/seller|owner|rep/i.test(actorId)) return 'Assigned seller'
  if (/system|service|worker|monitor/i.test(actorId)) return 'System process'
  return 'Team member'
}

export function safeRecordTitle(value: string | null | undefined, fallback: string): string {
  if (!value) return fallback
  const withoutEnvironmentPrefix = value.replace(/^\s*(?:\[?SAMPLE\]?|POC)\s*[:\-–—]?\s*/i, '')
  const withoutUuid = withoutEnvironmentPrefix.replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi, '').replace(/\s{2,}/g, ' ').trim()
  return withoutUuid && !identifierPattern.test(withoutUuid) ? withoutUuid : fallback
}

export function canonicalReference(value: string | null | undefined, fallback = 'Reference available in supporting evidence'): string {
  if (!value || identifierPattern.test(value)) return fallback
  return value
}

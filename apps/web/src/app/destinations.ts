import type { Surface } from './navigation'

export type NavigationCapability = 'authenticated' | 'source_health'
export type NavigationPlacement = 'primary' | 'secondary'

export interface NavigationDestination {
  surface: Surface
  label: string
  route: `#/${Surface}`
  job: string
  requiredCapability: NavigationCapability
  desktop: NavigationPlacement
  mobile: NavigationPlacement
  group: 'commercial' | 'administration' | 'personal'
}

export interface NavigationAuthority {
  authenticated: boolean
  sourceHealth: boolean
}

export const NAVIGATION_DESTINATIONS: readonly NavigationDestination[] = [
  { surface: 'today', label: 'Today', route: '#/today', job: 'Review the next commercial decisions.', requiredCapability: 'authenticated', desktop: 'primary', mobile: 'primary', group: 'commercial' },
  { surface: 'opportunities', label: 'Opportunities', route: '#/opportunities', job: 'Evaluate specific expansion and prospecting pursuits.', requiredCapability: 'authenticated', desktop: 'primary', mobile: 'primary', group: 'commercial' },
  { surface: 'accounts', label: 'Profiles', route: '#/accounts', job: 'Investigate organizations and account work.', requiredCapability: 'authenticated', desktop: 'primary', mobile: 'primary', group: 'commercial' },
  { surface: 'intelligence', label: 'Intelligence', route: '#/intelligence', job: 'Review public developments, market shifts, and account implications.', requiredCapability: 'authenticated', desktop: 'primary', mobile: 'primary', group: 'commercial' },
  { surface: 'map', label: 'Map', route: '#/map', job: 'Explore organizations, facilities, and nearby opportunities.', requiredCapability: 'authenticated', desktop: 'primary', mobile: 'primary', group: 'commercial' },
  { surface: 'actions', label: 'Actions', route: '#/actions', job: 'Manage assigned follow-ups and approvals.', requiredCapability: 'authenticated', desktop: 'primary', mobile: 'primary', group: 'commercial' },
  { surface: 'communications', label: 'Communications', route: '#/communications', job: 'Draft and review controlled communications.', requiredCapability: 'authenticated', desktop: 'primary', mobile: 'secondary', group: 'commercial' },
  { surface: 'monitor', label: 'Source Health', route: '#/monitor', job: 'Inspect collection, provider, scheduler, and coverage health.', requiredCapability: 'source_health', desktop: 'primary', mobile: 'secondary', group: 'administration' },
  { surface: 'settings', label: 'Settings', route: '#/settings', job: 'Manage personal preferences and authorized workspace details.', requiredCapability: 'authenticated', desktop: 'secondary', mobile: 'secondary', group: 'personal' },
] as const

export function authorizedDestinations(authority: NavigationAuthority): NavigationDestination[] {
  if (!authority.authenticated) return []
  return NAVIGATION_DESTINATIONS.filter(destination => destination.requiredCapability === 'authenticated' || authority.sourceHealth)
}

export function canOpenDestination(surface: Surface, authority: NavigationAuthority): boolean {
  return authorizedDestinations(authority).some(destination => destination.surface === surface)
}

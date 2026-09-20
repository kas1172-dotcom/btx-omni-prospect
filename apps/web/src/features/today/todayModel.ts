import type { CommandPriorityItem } from '../../types/api'
import { assessmentAttention } from '../../components/attentionModel'

export function greetingFor(date: Date): string {
  const hour = date.getHours()
  if (hour >= 5 && hour < 12) return 'Good morning'
  if (hour >= 12 && hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export function isHighImportance(item: CommandPriorityItem): boolean {
  return item.signal_brief
    ? assessmentAttention(item.signal_brief) === 'HIGH'
    : item.severity?.toUpperCase() === 'HIGH'
}

export function attentionFor(item: CommandPriorityItem): 'HIGH' | 'MEDIUM' | 'LOW' | 'UNAVAILABLE' {
  if (isHighImportance(item)) return 'HIGH'
  if (item.signal_brief) return assessmentAttention(item.signal_brief)
  return ['HIGH', 'MEDIUM', 'LOW'].includes(item.severity ?? '')
    ? item.severity as 'HIGH' | 'MEDIUM' | 'LOW'
    : 'UNAVAILABLE'
}

export function localDateLabel(value?: string): string | undefined {
  if (!value) return undefined
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split('-').map(Number)
    return new Date(year, month - 1, day).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }
  return new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

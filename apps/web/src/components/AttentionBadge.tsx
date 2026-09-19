import { StatusBadge } from './UI'
import type { AttentionLevel } from './attentionModel'

const labels: Record<AttentionLevel, string> = {
  HIGH: 'High importance',
  MEDIUM: 'Medium importance',
  LOW: 'Low importance',
  UNAVAILABLE: 'Importance not yet determined',
}

export function AttentionBadge({ level, label }: { level: AttentionLevel; label?: string }) {
  return <StatusBadge value={level} kind="priority" label={label ?? labels[level]} />
}

import { forwardRef, useEffect, useLayoutEffect, useId, useRef, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type RefObject, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import './ui.css'
import { presentationLabel } from './presentation'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive'
type ButtonSize = 'compact' | 'touch' | 'icon'

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize; loading?: boolean }>(function Button({ variant = 'secondary', size = 'compact', loading = false, disabled, className = '', children, ...props }, ref) {
  return <button {...props} ref={ref} className={`ui-button ui-button-${variant} ui-button-${size} ${className}`.trim()} disabled={disabled || loading} aria-busy={loading || undefined}>{loading && <span className="ui-button-spinner" aria-hidden="true" />}{loading ? <span>Loading…</span> : children}</button>
})

export function IconButton({ label, children, ...props }: Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> & { label: string; children: ReactNode }) { return <Button {...props} size="icon" aria-label={label}>{children}</Button> }

type FieldProps = { label?: string; helper?: string; error?: string }
function Field({ label, helper, error, id, children }: FieldProps & { id: string; children: ReactNode }) { return <label className={`ui-field ${error ? 'ui-field-error' : ''}`} htmlFor={id}>{label && <span className="ui-field-label">{label}</span>}{children}{error ? <span className="ui-field-message" role="alert">{error}</span> : helper ? <span className="ui-field-message">{helper}</span> : null}</label> }

export const TextInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & FieldProps>(function TextInput({ label, helper, error, id: suppliedId, className = '', ...props }, ref) { const generatedId = useId(); const id = suppliedId ?? generatedId; return <Field label={label} helper={helper} error={error} id={id}><input {...props} id={id} ref={ref} className={`ui-input ${className}`.trim()} aria-invalid={Boolean(error) || undefined} /></Field> })
export const SearchInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & FieldProps>(function SearchInput(props, ref) { return <span className="ui-search"><span aria-hidden="true">⌕</span><TextInput {...props} ref={ref} type="search" /></span> })
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & FieldProps>(function Textarea({ label, helper, error, id: suppliedId, className = '', ...props }, ref) { const generatedId = useId(); const id = suppliedId ?? generatedId; return <Field label={label} helper={helper} error={error} id={id}><textarea {...props} id={id} ref={ref} className={`ui-input ui-textarea ${className}`.trim()} aria-invalid={Boolean(error) || undefined} /></Field> })
export function SelectInput({ label, helper, error, id: suppliedId, className = '', children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & FieldProps) { const generatedId = useId(); const id = suppliedId ?? generatedId; return <Field label={label} helper={helper} error={error} id={id}><select {...props} id={id} className={`ui-input ui-select ${className}`.trim()} aria-invalid={Boolean(error) || undefined}>{children}</select></Field> }

export function FilterTrigger({ active = false, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) { return <Button {...props} className="ui-filter-trigger" variant="secondary" aria-pressed={active}>{children}<span aria-hidden="true">⌄</span></Button> }
export function FilterChip({ selected = false, onClear, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean; onClear?: () => void }) { const removableLabel = onClear && typeof children === 'string' ? `Remove ${children} filter` : undefined; return <button {...props} type={props.type ?? 'button'} className={`ui-filter-chip ${selected ? 'selected' : ''}`} aria-label={props['aria-label'] ?? removableLabel} aria-pressed={selected} onClick={event => { props.onClick?.(event); if (onClear && selected) onClear() }}>{children}{onClear && selected && <span aria-hidden="true">×</span>}</button> }

type StatusKind = 'entity' | 'priority' | 'action' | 'evidence' | 'source' | 'integration' | 'relationship' | 'truth' | 'neutral'
type StatusTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'inverse'
const semanticTone = (value: string): StatusTone => { const normalized = value.toUpperCase().replaceAll(' ', '_'); if (normalized === 'CUSTOMER') return 'inverse'; if (['AVAILABLE', 'CONFIRMED', 'COMPLETED', 'APPROVED', 'BROWSER_VERIFIED', 'PUBLICLY_VERIFIED', 'LIVE_PUBLIC'].includes(normalized)) return 'success'; if (['INFERRED', 'MEDIUM', 'NEEDS_RESEARCH', 'AUTOMATION_BLOCKED', 'IN_PROGRESS', 'PENDING'].includes(normalized)) return 'warning'; if (['HIGH', 'HIGH_PRIORITY', 'CONFLICTING', 'STALE_QUOTE', 'CUSTOMER_INACTIVITY', 'CANCELED', 'RESTRICTED'].includes(normalized)) return 'danger'; if (['OPEN', 'INFORMATIONAL', 'CONNECTED'].includes(normalized)) return 'info'; return 'neutral' }
export function StatusBadge({ value, kind = 'neutral', tone, label }: { value: string; kind?: StatusKind; tone?: StatusTone; label?: string }) { return <span className={`state ui-status ui-status-${kind} ui-status-${tone ?? semanticTone(value)}`}>{label ?? presentationLabel(value, kind === 'action' ? 'workflow' : kind === 'relationship' ? 'relationship' : kind === 'evidence' || kind === 'truth' ? 'evidence' : kind === 'integration' || kind === 'source' ? 'provider' : 'general')}</span> }
export function State({ value }: { value: string }) { return <StatusBadge value={value} kind="truth" /> }

export function Panel({ title, children, action, variant = 'default', className = '' }: { title?: string; children: ReactNode; action?: ReactNode; variant?: 'default' | 'subdued' | 'elevated'; className?: string }) { return <section className={`panel ui-panel ui-panel-${variant} ${className}`.trim()}>{title && <header className="panel-head"><h2>{title}</h2>{action}</header>}{children}</section> }
export function StatTile({ label, value, detail, tone = 'neutral', className = '' }: { label: string; value: ReactNode; detail?: ReactNode; tone?: 'neutral' | 'info' | 'success' | 'warning' | 'danger'; className?: string }) { return <article className={`ui-stat ui-stat-${tone} ${className}`.trim()}><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article> }
export function MetadataRow({ label, value }: { label: ReactNode; value: ReactNode }) { return <div className="ui-metadata-row"><span>{label}</span><strong>{value}</strong></div> }
export function Notice({ tone = 'info', title, children }: { tone?: 'info' | 'warning' | 'danger'; title?: string; children: ReactNode }) { return <div className={`ui-notice ui-notice-${tone}`} role={tone === 'info' ? 'status' : 'alert'}>{title && <strong>{title}</strong>}<span>{children}</span></div> }

export function Disclosure({ title, children, defaultOpen = false, className = '', open: controlledOpen, onOpenChange }: { title: ReactNode; children: ReactNode; defaultOpen?: boolean; className?: string; open?: boolean; onOpenChange?: (open: boolean) => void }) {
  const [internalOpen, setInternalOpen] = useState(defaultOpen)
  const open = controlledOpen ?? internalOpen
  const id = useId()
  return <section className={`ui-disclosure ${className}`.trim()}><button type="button" className="ui-disclosure-trigger" aria-expanded={open} aria-controls={id} onClick={() => { setInternalOpen(!open); onOpenChange?.(!open) }}><span>{title}</span><span aria-hidden="true">{open ? '⌃' : '⌄'}</span></button>{open && <div className="ui-disclosure-body" id={id}>{children}</div>}</section>
}

export function EvidenceSource({ title, source, date, evidenceState, validationState, url, detail }: { title?: string; source?: string; date?: string; evidenceState?: string; validationState?: string; url?: string; detail?: ReactNode }) { const usableUrl = Boolean(url && /^https?:\/\//.test(url) && !url.includes('.invalid')); const unavailable = !source && !date && !usableUrl; return <article className="ui-evidence"><StatusBadge value={evidenceState ?? (unavailable ? 'NEEDS_RESEARCH' : 'PUBLIC EVIDENCE')} kind="evidence" tone={unavailable ? 'warning' : undefined} />{title && <strong>{title}</strong>}<div className="ui-evidence-meta"><span>Source: {source ?? 'Unavailable · needs research'}</span><span>Date: {date ?? 'Unavailable'}</span>{validationState && <span>Validation: {presentationLabel(validationState, 'evidence')}</span>}</div>{detail && <p>{detail}</p>}{usableUrl ? <a href={url} target="_blank" rel="noreferrer">Inspect source →</a> : <span className="ui-evidence-unavailable">Source link unavailable</span>}</article> }

export function ResponsiveTable({ label, header, children }: { label: string; header?: ReactNode; children: ReactNode }) { return <div className="ui-table" role="table" aria-label={label}>{header && <div className="ui-table-header" role="row">{header}</div>}<div role="rowgroup">{children}</div></div> }
export function SortableHeader({ children, direction = 'none', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { direction?: 'ascending' | 'descending' | 'none' }) { return <div role="columnheader" aria-sort={direction}><button {...props} className="ui-sort-header">{children}<span aria-hidden="true">{direction === 'ascending' ? '↑' : direction === 'descending' ? '↓' : '↕'}</span></button></div> }
export function TableRow({ children, selected = false, interactive = false, className = '' }: { children: ReactNode; selected?: boolean; interactive?: boolean; className?: string }) { return <div className={`ui-table-row ${selected ? 'selected' : ''} ${interactive ? 'interactive' : ''} ${className}`.trim()} role="row" aria-selected={selected || undefined}>{children}</div> }
export function MobileListRow({ title, metadata, tertiary, selected = false, onClick }: { title: ReactNode; metadata?: ReactNode; tertiary?: ReactNode; selected?: boolean; onClick?: () => void }) { const content = <><strong>{title}</strong>{metadata && <span>{metadata}</span>}{tertiary && <small>{tertiary}</small>}</>; return onClick ? <button type="button" className={`ui-mobile-row ${selected ? 'selected' : ''}`} aria-pressed={selected} onClick={onClick}>{content}</button> : <article className={`ui-mobile-row ${selected ? 'selected' : ''}`}>{content}</article> }

export function Drawer({ open, onClose, titleId, children, className = '', initialFocus }: { open: boolean; onClose: () => void; titleId: string; children: ReactNode; className?: string; initialFocus?: RefObject<HTMLElement | null> }) {
  const dialog = useRef<HTMLElement>(null)
  const closeRef = useRef(onClose)
  useEffect(() => { closeRef.current = onClose }, [onClose])
  useLayoutEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    // Focus before paint, never from a late timer that can steal a user's first
    // keystroke or race an input operation (notably in WebKit).
    const target = initialFocus?.current ?? dialog.current?.querySelector<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])')
    if (target && dialog.current?.contains(target)) target.focus()
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); closeRef.current(); return }
      if (event.key !== 'Tab' || !dialog.current) return
      const items = [...dialog.current.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])')]
      if (!items.length) return
      const first = items[0]; const last = items.at(-1)!
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = previousOverflow; if (previouslyFocused?.isConnected) previouslyFocused.focus() }
  }, [open, initialFocus])
  if (!open) return null
  return <div className="drawer-backdrop ui-drawer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}><aside ref={dialog} className={`ui-drawer ${className}`.trim()} role="dialog" aria-modal="true" aria-labelledby={titleId}>{children}</aside></div>
}

export function StatusMessage({ state = 'empty', title, children, action }: { state?: 'empty' | 'loading' | 'error' | 'unavailable' | 'needs-research'; title?: string; children: ReactNode; action?: ReactNode }) { return <div className={`ui-status-message ui-status-message-${state}`} role={state === 'error' ? 'alert' : 'status'} aria-live={state === 'loading' ? 'polite' : undefined}>{state === 'loading' && <span className="ui-state-spinner" aria-hidden="true" />}{title && <strong>{title}</strong>}<span>{children}</span>{action}</div> }
export function Empty({ children }: { children: ReactNode }) { return <StatusMessage state="empty">{children}</StatusMessage> }

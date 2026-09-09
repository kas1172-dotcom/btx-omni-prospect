/** Readable, non-executable rendering shared by evidence inspectors and Omni. */
export function CanonicalRecord({ value }: { value: unknown }) {
  if (value == null) return <span>Unknown</span>
  if (Array.isArray(value)) return <ul>{value.map((item, index) => <li key={index}><CanonicalRecord value={item} /></li>)}</ul>
  if (typeof value === 'object') return <dl>{Object.entries(value).map(([key, item]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd><CanonicalRecord value={item} /></dd></div>)}</dl>
  if (typeof value === 'string' && /^https:\/\//i.test(value)) return <a href={value} target="_blank" rel="noreferrer">{value}</a>
  return <span>{String(value)}</span>
}

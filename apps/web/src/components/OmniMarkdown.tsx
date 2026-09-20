import { Fragment } from 'react'
import { safeChatLink } from './omniText'

function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*|\[[^\]]+\]\([^\s)]+\))/g).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>
    const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part)
    const url = link && safeChatLink(link[2])
    return link && url ? <a key={index} href={url} target="_blank" rel="noopener noreferrer">{link[1]}</a> : <Fragment key={index}>{part}</Fragment>
  })
}

export function OmniMarkdown({ text }: { text: string }) {
  // React text nodes escape all raw HTML. No HTML parser or innerHTML is used.
  return <>{text.split(/\n\s*\n/).map((block, index) => {
    const lines = block.split('\n')
    if (lines.every(line => /^\s*(?:[-*]|\d+\.)\s/.test(line))) return <ul key={index}>{lines.map((line, i) => <li key={i}>{inline(line.replace(/^\s*(?:[-*]|\d+\.)\s/, ''))}</li>)}</ul>
    return <p key={index}>{inline(block)}</p>
  })}</>
}

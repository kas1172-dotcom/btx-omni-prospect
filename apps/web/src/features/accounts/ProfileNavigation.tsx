import { useContext, useState, type ReactNode } from 'react'
import { ProfileTabContext, profileTabs, type ProfileTab } from './profileTabs'

// Keep visited sections mounted to preserve drafts; do not load unseen modules.
export function ProfilePage({ tab, children }: { tab: ProfileTab; children: ReactNode }) {
  const active = useContext(ProfileTabContext) === tab
  const [visited, setVisited] = useState(active)
  if (active && !visited) setVisited(true)
  return active || visited ? <div className="profile-page-section" hidden={!active}>{children}</div> : null
}

export function ProfileTabs({ selected, onSelect }: { selected: ProfileTab; onSelect: (tab: ProfileTab) => void }) {
  return <div className="profile-tabs" role="tablist" aria-label="Profile sections">{profileTabs.map((tab, index) => <button key={tab} type="button" role="tab" id={`profile-tab-${tab}`} aria-controls="profile-tab-content" aria-selected={selected === tab} tabIndex={selected === tab ? 0 : -1} onClick={() => onSelect(tab)} onKeyDown={event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? profileTabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + profileTabs.length) % profileTabs.length
    onSelect(profileTabs[next]); document.getElementById(`profile-tab-${profileTabs[next]}`)?.focus()
  }}>{tab}</button>)}</div>
}

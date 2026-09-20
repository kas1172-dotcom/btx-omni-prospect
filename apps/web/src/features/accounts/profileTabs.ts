import { createContext } from 'react'

export const profileTabs = ['Overview', 'Opportunities', 'Commercial', 'Intelligence', 'Relationships', 'More'] as const
export type ProfileTab = typeof profileTabs[number]
export const ProfileTabContext = createContext<ProfileTab>('Overview')

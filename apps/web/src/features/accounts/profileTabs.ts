import { createContext } from 'react'

export const profileTabs = ['Overview', 'Commercial', 'Intelligence', 'Actions', 'Relationships', 'More'] as const
export type ProfileTab = typeof profileTabs[number]
export const ProfileTabContext = createContext<ProfileTab>('Overview')

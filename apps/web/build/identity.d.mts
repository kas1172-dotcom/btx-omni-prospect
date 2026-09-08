export interface FrontendBuildIdentity {
  repository: string;
  commit_sha: string | null;
  git_tree: string | null;
  worktree: 'clean' | 'dirty' | 'unknown';
  identity_state: string;
  built_at: string;
}
export function readBuildIdentity(env?: Record<string, string | undefined>, git?: (args: string[]) => string | null): FrontendBuildIdentity;

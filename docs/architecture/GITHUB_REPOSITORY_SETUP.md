# GitHub repository setup

Create the standalone repository as **`btx-omni-prospect`** with **private**
visibility and make `main` the default branch.

## Recommended settings

- Require pull requests before merging to `main`.
- Require the **POC CI** workflow to pass before merge.
- Disallow force pushes to `main`.
- Require conversation resolution where the organization uses reviews.
- Delete head branches after merge.
- Enable Dependabot alerts and security updates; enable version updates if the
  organization wants routine dependency pull requests.
- Enable secret scanning and push protection where the GitHub plan supports it.
- Disable the GitHub Wiki unless it becomes an explicitly maintained knowledge base.

## Repository metadata

Use this description:

> BTX Omni Prospect is a governed commercial intelligence and prospecting platform combining BTX commercial context, public market intelligence, deterministic scoring/matching, geographic prospecting, and human-approved seller workflows.

Add these topics:

`commercial-intelligence`, `prospecting`, `fastapi`, `react`, `postgres`, `ai`, `btx`.

## First remote

After creating the private repository, add its HTTPS or SSH URL as `origin` and
push `main` only after confirming the destination and repository visibility:

```powershell
git remote add origin <repository-url>
git push -u origin main
```

This repository intentionally contains no production secrets. Configure
`DATABASE_URL` (or `BTX_DATABASE_URL`) and `BTX_FRONTEND_ORIGINS` in the target
deployment environment.

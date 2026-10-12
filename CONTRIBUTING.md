# Contributing

## Development

Use Node.js 24.21.0 (pinned in .node-version) and npm 12.2.0 (pinned in packageManager), following Dewbow's toolchain. Use the committed package-lock.json and TypeScript 7.0.2 with @types/node 24.19.2. Read AGENTS.md and docs/ before changing code.

```sh
npm ci
npm run build
npm run typecheck
npm test
git diff --check
```

The tests use Node's built-in test runner and synthetic data, with real HTTP and WebSocket servers bound only to 127.0.0.1. They require no DingTalk credentials or external service connection. npm 12 blocks unapproved dependency installation scripts; allowScripts is empty because none are needed. Do not allow scripts without reviewing a concrete requirement. Runtime checks and commands belong in docs/; keep the root README brief.

## Commit checks

Install Gitleaks with support for its git command and a POSIX shell, then run:

```sh
sh scripts/install-hooks.sh
```

The installer enables .githooks locally and refuses to replace existing active hooks. Every clone needs activation. Missing tools or scan failures block commits; do not bypass hooks or weaken scans.

Use main as the default branch. Review explicit staged paths, the complete staged diff, and git diff --cached --check before committing. Use Conventional Commits. Preserve unrelated changes. Pushes, pull requests, and deployments require authorization within the current task scope.

## Local data

Keep credentials, real message payloads, session webhooks, private logs, machine-specific paths, and runtime state out of commits. Use placeholders and synthetic fixtures. Local outputs belong in ignored work/, outputs/, logs/, or state/ directories. Ignore rules do not protect already tracked files.

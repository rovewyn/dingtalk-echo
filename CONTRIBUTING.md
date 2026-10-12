# Contributing

## Development

This repository is initialized for policy review. Bot implementation and runtime/dependency selection are pending. Read AGENTS.md and docs/ before changing code. Document reproducible setup and validation commands when implementation begins.

## Commit checks

Install Gitleaks with support for its git command and a POSIX shell, then run:

```sh
sh scripts/install-hooks.sh
```

The installer enables .githooks locally and refuses to replace existing active hooks. Every clone needs activation. Missing tools or scan failures block commits; do not bypass hooks or weaken scans.

Use main as the default branch. Review explicit staged paths, the complete staged diff, and git diff --cached --check before committing. Use Conventional Commits. Preserve unrelated changes. Pushes, pull requests, and deployments require authorization within the current task scope.

## Local data

Keep credentials, real message payloads, session webhooks, private logs, machine-specific paths, and runtime state out of commits. Use placeholders and synthetic fixtures. Local outputs belong in ignored work/, outputs/, logs/, or state/ directories. Ignore rules do not protect already tracked files.

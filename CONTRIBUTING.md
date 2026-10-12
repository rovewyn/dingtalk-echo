# Contributing

## Development

Use Python 3.13.16 (pinned in .python-version) and uv 0.13.0. Dependencies are resolved in uv.lock, including dingtalk-stream 0.24.3. Read AGENTS.md and docs/ before changing code.

```sh
uv sync --locked
uv run --locked python -m unittest discover -s tests -v
uv run --locked python -m compileall -q echo_bot.py tests
git diff --check
```

The tests use synthetic data and include real HTTP and WebSocket servers bound only to 127.0.0.1. They require no DingTalk credentials or external service connection. Runtime checks and commands belong in docs/; keep the root README brief.

## Commit checks

Install Gitleaks with support for its git command and a POSIX shell, then run:

```sh
sh scripts/install-hooks.sh
```

The installer enables .githooks locally and refuses to replace existing active hooks. Every clone needs activation. Missing tools or scan failures block commits; do not bypass hooks or weaken scans.

Use main as the default branch. Review explicit staged paths, the complete staged diff, and git diff --cached --check before committing. Use Conventional Commits. Preserve unrelated changes. Pushes, pull requests, and deployments require authorization within the current task scope.

## Local data

Keep credentials, real message payloads, session webhooks, private logs, machine-specific paths, and runtime state out of commits. Use placeholders and synthetic fixtures. Local outputs belong in ignored work/, outputs/, logs/, or state/ directories. Ignore rules do not protect already tracked files.

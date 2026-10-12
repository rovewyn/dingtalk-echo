# Repository Guidelines

## Project Scope

Build a minimal DingTalk echo bot. The first milestone is a direct chat: receive a text message and reply with the same text through an enterprise internal application robot using Stream mode. Group chat support, when implemented, handles messages addressed to the robot.

Keep the first version small. Do not add an LLM, database, conversation memory, Web UI, or additional platform integrations unless requested. Use TypeScript with the Node.js, npm, ESM, strict compiler settings, and built-in test runner used by Dewbow. Keep this repository a single package. Verify the official DingTalk Stream protocol and SDK interfaces before integration changes, and document the selected runtime and dependency versions.

Separate platform message handling from the echo operation only where it makes the code easier to understand. Preserve platform-delivered text, including Unicode and line breaks. Define non-text handling explicitly. Acknowledge callbacks according to the official Stream contract, handle reply failures, and consider duplicate callback delivery without promising exactly-once delivery unless verified.

Do not log message contents, application secrets, access tokens, or session webhook URLs by default. Use synthetic messages for automated checks. Live DingTalk testing uses the user's authorized application and conversation; record the outcome without publishing private payloads.

## Project Structure & Module Organization

Read the repository's entry-point documentation and applicable directory-level instructions before making changes. Inspect the existing structure, dependency manifests, lockfiles, and available commands. Do not assume a framework, runtime, package manager, or deployment platform.

Read `CONTRIBUTING.md` for contributor setup and the commit workflow. After cloning, install Gitleaks with support for the `git` command and run `sh scripts/install-hooks.sh` before making commits.

Keep the root `README.md` as simple as possible: a brief project introduction and a statement that documentation is in `docs/`. A link to the `docs/` directory is allowed. Do not link to individual documentation files from the root README unless the user explicitly requests those links. Put detailed setup, API, architecture, and usage documentation in files under `docs/`. Keep repository policy and contributor instructions in their corresponding root files, including `AGENTS.md` and `CONTRIBUTING.md`, with their full content.

Keep related code and resources together. Follow established directory boundaries and naming patterns. Update operating instructions when a change affects setup, configuration, commands, or expected behavior.

Keep generated files, caches, dependency installations, and temporary outputs out of version control unless the repository explicitly tracks them. Preserve user-created files and local results during cleanup.

## Setup & Development Commands

Use the repository's documented runtime versions, package manager, and lockfiles. Prefer existing scripts and reproducible installation commands. Avoid changing dependencies or introducing tools without a clear need for the task.

Use the documented build, development, preview, and validation commands. If commands are missing, inspect the project before choosing them. Document reusable commands and required environment variable names without including secret values.

Run `git diff --check` when reviewing changes and `git diff --cached --check` before committing.

## Coding Style & Naming Conventions

Match the surrounding code and the conventions of each language. Use descriptive names, keep changes focused, and reuse existing abstractions before adding new ones.

Use English for repository documentation, code comments, and other written project artifacts.

Use camelCase for project-owned TypeScript variables, functions, methods, properties, and configuration keys. Preserve DingTalk-defined field names at integration boundaries. Use .js suffixes in relative ESM imports and keep @types/node on the selected Node.js runtime's major version.

Preserve public interfaces and established behavior unless the task requires a change. Explain non-obvious constraints, lifecycle assumptions, and tradeoffs where they affect maintenance.

For user interfaces, preserve semantic content, accessibility, and responsive behavior. Release resources when their owner is torn down.

For retained generated assets, preserve source outputs and record exact prompts, exposed tool parameters, and integration notes. Do not invent model names, versions, seeds, or other unavailable metadata. Remove unused assets and temporary design files created by the task.

## Early Development Compatibility

The project is in early development. Do not introduce backward compatibility layers, data migrations, or protocol version negotiation without a concrete requirement. Preserve credentials, real messages, and unrelated user files during any local state reset.

## Validation Guidelines

Choose validation that matches the change and the repository's existing practices. Run relevant checks and inspect the affected behavior directly.

Write only the minimum necessary unit tests. Add a unit test only when it protects critical behavior or a meaningful regression that existing checks do not cover. Reuse or extend existing tests before adding new ones. Do not add tests for trivial code, simple getters or formatting, or tests that merely repeat the implementation. Do not increase test count or coverage for its own sake.

For visual changes, inspect the result in the target application or browser. Check relevant viewport sizes, interaction states, and accessibility behavior. Use manual visual review where automated checks cannot establish correctness.

Record the commands run, their results, and any checks that were skipped. Distinguish local verification, simulated observations, real environment execution, and deployed acceptance. Do not claim broader success than the available evidence supports.

## Local Preview

When the task includes a local preview, open it for the user and share its URL. Prefer a loopback address and use an available port.

Starting a preview does not authorize a push, merge, or deployment.

## Git Workflow & Cleanup

Before editing, inspect the current branch, working tree, upstream, and remote default branch. Refresh remote references when available. Preserve uncommitted changes and unrelated work; do not reset or overwrite them to obtain a clean checkout.

Keep commits focused on the requested change.

After a pull request is merged, remove its local and remote feature branches:

1. Confirm the pull request is merged and neither branch contains new or unmerged work. For squash merges, verify that all branch changes are present in the remote default branch.
2. Delete the remote feature branch, then run `git fetch --prune <remote>`.
3. Switch away from the local feature branch. In a primary clone, switch to the default branch and update it with `git merge --ff-only <remote>/<default-branch>`. In a linked worktree, use `git switch --detach <remote>/<default-branch>`.
4. Delete the local feature branch and verify that both feature branches are gone.

Preserve branches used by other worktrees. If cleanup would affect unrelated work, leave the affected branch in place and report the reason.

As part of post-merge cleanup, stop local preview servers started for that pull request. Verify that the processes have exited and their listening ports have been released. Preserve previews still used by other ongoing work or explicitly requested to remain running.

## Commit & Pull Request Guidelines

Use Conventional Commits for commit messages and pull request titles: `type(scope): description`, with an optional scope.

Describe the problem, resulting behavior, and purpose of the change. Include relevant validation results, disclose omitted checks, and link issues when applicable. Keep descriptions focused on the final implementation.

Review staged files before committing. Honor repository-specific restrictions on reports, measurements, screenshots, logs, and other outputs before including them in commits or pull requests.

Stage only the files required for the current change. Inspect `git diff --cached --name-status` and `git diff --cached` before committing. Keep unrelated or unfinished work uncommitted.

## Security & Configuration

Never commit credentials, tokens, cookies, private profiles, personal data, or machine-specific configuration. Use synthetic data and placeholders in examples. Redact sensitive information before sharing logs, screenshots, URLs, or reports.

Never include machine-specific absolute filesystem paths from a real local environment in committed content. Use repository-relative paths, environment variables, or generic placeholders instead. Standard platform paths required by code or tooling, including system library paths and interpreter shebangs, and clearly synthetic paths used in tests or examples are allowed.

Never include the current local operating system user's real name or username in committed content. Redact it or use a generic placeholder instead. This rule applies to all files included in a commit, including source files, documentation, configuration examples, fixtures, and retained generated assets.

Keep local environment files, Codex session exports, databases, machine paths, runtime state, raw logs, screenshots, and measured results out of commits and pull requests. Use the ignored local output directories listed in `CONTRIBUTING.md`. Commit only synthetic fixtures and configuration examples with placeholder values. Publishing local results requires explicit user authorization and a separate review for sensitive data.

Run all configured commit hooks and security checks. Missing required tools, scan errors, or findings block commits. Do not bypass hooks with `--no-verify`; fix the issue, restage changes, and rerun the checks.

Every commit must pass the versioned pre-commit hook, including `git diff --cached --check` and `gitleaks git --pre-commit --staged --redact`. Gitleaks scans for secrets; it does not replace the staged-file review for personal data, machine-specific paths, or local results. Do not weaken the scan or add exclusions to make a finding pass.

Review relevant security policies when changing resource loading, permissions, or external integrations. Keep development-only exceptions out of production configuration.

Treat publishing, deployment, shared environment changes, and release configuration as separate operations. Perform them only within the user's authorized scope.

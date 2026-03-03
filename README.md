# Coding Workspace Codex Harness Template

Minimal template for a repo-cloning coding workspace that runs Codex via the Codex CLI.

## Note

**The SDK + MCP server path does not currently support the latest Codex models (including `codex-5.3-pro`), so this template uses Codex CLI instead.**

- Use `codex/config.yaml` (baked to `/app/codex/config.yaml`) as the source of truth for Codex runtime settings.

## What this template does

- Clones the target repository into `/workspace`.
- Optionally boots GitHub CLI auth when a token is provided.
- Supports optional `git_author_email` task param for commit author/committer email.
- Mounts a vanilla Codex config file at `/workspace/.codex/config.yaml`.
- Reads model/sandbox/approval settings from `/app/codex/config.yaml` in `on_event`.
- Runs `codex exec` and `codex exec resume` (JSON mode) to preserve thread state across task events.

## Runtime

- `sdk_type: codex_agent_sdk`
- Codex CLI (`@openai/codex`) preinstalled
- `git`, `gh`, `node`, and `npm` available in the container

## OpenAI Docs

- Multi-agent (Codex CLI): https://developers.openai.com/codex/multi-agent
- MCP with Codex CLI: https://developers.openai.com/codex/mcp
- AGENTS.md guide: https://developers.openai.com/codex/guides/agents-md
- Config basics: https://developers.openai.com/codex/config-basic
- Config advanced: https://developers.openai.com/codex/config-advanced
- Config reference: https://developers.openai.com/codex/config-reference
- Config sample: https://developers.openai.com/codex/config-sample
- Agents SDK guide (background/reference): https://developers.openai.com/codex/guides/agents-sdk/

## Mounted Codex Config

- Source in image: `/app/codex/config.yaml` (from repo path `codex/config.yaml`)
- Mounted target: `/workspace/.codex/config.yaml` (configured in `config.yaml` sandbox mounts)

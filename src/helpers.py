"""Helper utilities for the Coding Workspace Codex Agent."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from pathlib import Path

from terminaluse.lib import TaskContext, make_logger

NOISY_RUNTIME_LOGGERS = (
    "httpx",
    "httpcore",
    "uvicorn.access",
    "terminaluse.lib.telemetry",
    "terminaluse.lib.sdk.fastacp",
    "opentelemetry",
    "opentelemetry.instrumentation",
)

WORKSPACE_DIR = "/workspace"
WORKSPACE_PATH = Path(WORKSPACE_DIR)
WORKSPACE_GIT_PATH = WORKSPACE_PATH / ".git"


def _env_log_level(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip().upper()
    if not raw:
        return default
    return getattr(logging, raw, default)


def configure_runtime_logging() -> None:
    """Reduce infra noise while keeping agent-level signal visible."""
    app_level = _env_log_level("AGENT_APP_LOG_LEVEL", logging.INFO)
    infra_level = _env_log_level("AGENT_INFRA_LOG_LEVEL", logging.WARNING)
    logging.getLogger().setLevel(app_level)
    for logger_name in NOISY_RUNTIME_LOGGERS:
        logging.getLogger(logger_name).setLevel(infra_level)


logger = make_logger(__name__)


def run_cmd(
    args: list[str],
    *,
    cwd: str | None = None,
    timeout: int = 120,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command."""
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def git_env() -> dict[str, str]:
    """Get environment with git prompts disabled."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    return env


def build_authenticated_clone_url(
    repo_url: str, github_token: str | None
) -> tuple[str, bool]:
    """Return a clone URL with embedded token when cloning from GitHub HTTPS."""
    if (
        not github_token
        or not repo_url.startswith("https://github.com/")
        or "@" in repo_url.split("://", 1)[1]
    ):
        return repo_url, False
    authed = repo_url.replace(
        "https://github.com/",
        f"https://x-access-token:{github_token}@github.com/",
        1,
    )
    return authed, True


def redact_secret(text: str, secret: str | None) -> str:
    """Replace secret with *** in text."""
    if not secret:
        return text
    return text.replace(secret, "***")


def configure_git_identity(
    github_login: str | None,
    git_author_email: str | None = None,
) -> None:
    """Set git user.name and user.email for repository commits."""
    name = github_login or "TerminalUse Agent"
    default_email = (
        f"{github_login}@users.noreply.github.com"
        if github_login
        else "terminaluse-agent@users.noreply.github.com"
    )
    email = git_author_email.strip() if git_author_email else default_email
    run_cmd(["git", "config", "user.name", name], cwd=WORKSPACE_DIR)
    run_cmd(["git", "config", "user.email", email], cwd=WORKSPACE_DIR)


def task_param_str(ctx: TaskContext, key: str) -> str | None:
    """Extract a string parameter from task params."""
    params = getattr(ctx.task, "params", None)
    if not isinstance(params, dict):
        return None
    value = params.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def task_metadata_str(ctx: TaskContext, key: str) -> str | None:
    """Extract a string value from task metadata."""
    metadata = getattr(ctx.task, "task_metadata", None)
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def task_slack_thread_context(ctx: TaskContext) -> tuple[str | None, str | None]:
    """Resolve Slack channel + thread context from params/metadata."""
    channel = task_param_str(ctx, "slack_channel") or task_metadata_str(
        ctx, "slack_channel"
    )
    thread_ts = task_param_str(ctx, "slack_thread_ts") or task_metadata_str(
        ctx, "slack_thread_ts"
    )
    if channel and thread_ts:
        return (channel, thread_ts)

    thread_key = task_param_str(ctx, "slack_thread_key") or task_metadata_str(
        ctx, "slack_thread_key"
    )
    if not thread_key:
        return (channel, thread_ts)

    parts = thread_key.split(":")
    if len(parts) < 3:
        return (channel, thread_ts)

    if not channel:
        candidate = parts[1].strip()
        if candidate:
            channel = candidate
    if not thread_ts:
        candidate = ":".join(parts[2:]).strip()
        if candidate:
            thread_ts = candidate
    return (channel, thread_ts)


def build_slack_mode_prompt(
    *,
    user_message: str,
    slack_channel: str | None,
    slack_thread_ts: str | None,
) -> str:
    """Prepend a strict Slack thread response contract when context exists."""
    if not slack_channel or not slack_thread_ts:
        return user_message

    return (
        "[Slack thread response contract]\n"
        "- This task originated from a Slack thread.\n"
        f"- slack_channel: {slack_channel}\n"
        f"- slack_thread_ts: {slack_thread_ts}\n"
        "- REQUIRED: before ending this turn, post at least one user-visible reply in that Slack thread.\n"
        "- REQUIRED: include a short summary of what you changed or checked.\n"
        "- REQUIRED: if blocked/failing, post the exact blocker in that thread before ending.\n"
        "- Use the using-slack-tools skill script at /app/skills/using-slack-tools/scripts/slack_tools.py.\n"
        "- Do not rely only on Terminal Use output; the user reads Slack.\n"
        "[/Slack thread response contract]\n\n"
        "[User request]\n"
        f"{user_message}"
    )


def workspace_ready() -> bool:
    """Check if workspace has a git repository."""
    return WORKSPACE_GIT_PATH.exists()


async def wait_for_workspace_ready(
    *,
    timeout_seconds: float = 45.0,
    poll_seconds: float = 0.5,
) -> bool:
    """Wait for workspace to be ready (git repo exists)."""
    deadline = time.monotonic() + max(1.0, timeout_seconds)
    while time.monotonic() <= deadline:
        if workspace_ready():
            return True
        await asyncio.sleep(max(0.05, poll_seconds))
    return workspace_ready()

r"""Minimal GitHub Copilot SDK connection test for AutoDoc.

Run after signing in to Copilot, or with COPILOT_GITHUB_TOKEN/GH_TOKEN/GITHUB_TOKEN:

    .venv\Scripts\python.exe test_copilot_connection.py
"""

from autodoc.ai import CopilotAIProvider
from autodoc.ai.copilot import CopilotConfigurationError


def main() -> None:
    provider = CopilotAIProvider.from_env()
    try:
        response = provider.complete_sync(
            "Reply with one short sentence confirming the AutoDoc Copilot SDK connection works."
        )
    except CopilotConfigurationError as exc:
        raise SystemExit(str(exc)) from exc
    print(response)


if __name__ == "__main__":
    main()

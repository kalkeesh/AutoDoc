import asyncio
import os
import sys

from copilot import CopilotClient


async def main():
    token = os.getenv("COPILOT_GITHUB_TOKEN") or None
    client = CopilotClient(github_token=token, use_logged_in_user=token is None)
    await client.start()
    try:
        status = await client.get_auth_status()
    finally:
        await client.stop()

    print(f"Authenticated: {status.isAuthenticated}")
    print(f"Login: {status.login or 'unknown'}")
    print(f"Auth type: {status.authType or 'unknown'}")
    if status.statusMessage:
        print(f"Message: {status.statusMessage}")

    return 0 if status.isAuthenticated else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

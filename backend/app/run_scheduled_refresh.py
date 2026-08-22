from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]

# LaunchAgents do not inherit the interactive shell environment.
# Load backend/.env here so the entire V112 subprocess tree
# inherits DATABASE_URL and other application settings.
load_dotenv(
    BASE_DIR / ".env",
    override=False,
)

os.environ["PYTHONUNBUFFERED"] = "1"

LOCK_DIR = BASE_DIR / "data"
LOCK_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LOCK_PATH = (
    LOCK_DIR
    / "v112_refresh.lock"
)


def main():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError(
            "DATABASE_URL is missing after loading backend/.env"
        )

    print(
        "[ENV READY]",
        "DATABASE_URL loaded from application environment",
    )

    with LOCK_PATH.open("w") as lock_file:

        try:
            fcntl.flock(
                lock_file.fileno(),
                fcntl.LOCK_EX
                | fcntl.LOCK_NB,
            )

        except BlockingIOError:
            print(
                "[SKIP] Another V112 refresh "
                "is already running."
            )
            return

        print(
            "[LOCK ACQUIRED]",
            LOCK_PATH,
        )

        # ==================================================
        # CRITICAL PATH: refresh existing production sources
        # ==================================================

        print(
            "[SCHEDULED STEP]",
            "V112 production refresh",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-u",
                "-m",
                "app.run_v112_refresh_pipeline",
            ],
            check=False,
        )

        if result.returncode != 0:
            print(
                "[SCHEDULED FAILURE]",
                "V112 production refresh",
                "| exit=",
                result.returncode,
            )

            raise SystemExit(
                result.returncode
            )

        print(
            "[SCHEDULED SUCCESS]",
            "V112 production refresh",
        )

        # ==================================================
        # BEST-EFFORT PATH: grow the employer/source registry
        #
        # V114 owns:
        # - its 24-hour cooldown
        # - bounded discovery
        # - bounded verification
        # - subprocess timeouts
        #
        # Employer onboarding must never turn a successful
        # production refresh into a failed scheduled run.
        # ==================================================

        print(
            "[SCHEDULED STEP]",
            "V114 bounded employer growth",
        )

        growth = subprocess.run(
            [
                sys.executable,
                "-u",
                "-m",
                "app.run_employer_auto_onboarding",
                "--create-batch",
                "--new-batch-name",
                "AUTO_ONBOARDING",
                "--batch-limit",
                "25",
                "--discovery-limit",
                "5",
                "--verification-limit",
                "5",
                "--min-interval-hours",
                "24",
            ],
            check=False,
        )

        if growth.returncode == 0:
            print(
                "[SCHEDULED SUCCESS]",
                "V114 bounded employer growth",
            )
        else:
            print(
                "[SCHEDULED WARNING]",
                "V114 employer growth failed",
                "| exit=",
                growth.returncode,
                "| production refresh remains successful",
            )

        print(
            "[SCHEDULED REFRESH COMPLETE]"
        )


if __name__ == "__main__":
    main()

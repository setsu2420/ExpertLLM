"""Standalone runner for semantic question trending job.

Run this in a dedicated container or process; it will execute the
question trending job every 2 hours.
"""
from __future__ import annotations

import time
import sys

from app import app
from services.question_trending_task import run_question_trending_job
import config


def main() -> None:
    with app.app_context():
        print(
            f"[QuestionTrending] runner started with interval = "
            f"{config.QUESTION_TRENDING_INTERVAL_SECONDS} seconds",
            flush=True,
        )
        while True:
            print("[QuestionTrending] ====================Job started====================", flush=True)
            try:
                run_question_trending_job()
            except Exception as e:  # noqa: BLE001
                print(f"[QuestionTrending] job error: {e}", file=sys.stderr, flush=True)
            print("[QuestionTrending] ====================Job finished====================", flush=True)
            # sleep configured interval
            time.sleep(max(1, config.QUESTION_TRENDING_INTERVAL_SECONDS))


if __name__ == "__main__":
    main()

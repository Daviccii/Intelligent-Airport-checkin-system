#!/usr/bin/env python3
"""RQ worker tasks for the Intelligent Airport check-in system.

This module exposes functions that the RQ worker will import and execute.
It keeps tasks minimal and re-uses the server's send function where possible.
"""
import os
import sys
from pathlib import Path

# Ensure backend package imports work when run inside container or locally
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import send_boarding_pass_email  # re-use existing function


def enqueue_send_boarding_pass(passport: str, email: str = None):
    """Wrapper task to call the send_boarding_pass_email function from the app.
    RQ will execute this function with provided args.
    """
    # send_boarding_pass_email may expect more context; call defensively
    try:
        send_boarding_pass_email(passport, email=email)
    except TypeError:
        # older signature: send_boarding_pass_email(passport)
        send_boarding_pass_email(passport)


if __name__ == '__main__':
    # Convenience: allow running a single task from CLI for dev/debug
    if len(sys.argv) >= 2:
        passport = sys.argv[1]
        email = sys.argv[2] if len(sys.argv) >= 3 else None
        print(f"Running enqueue_send_boarding_pass(passport={passport}, email={email})")
        enqueue_send_boarding_pass(passport, email)
    else:
        print("This script is intended to be used by RQ workers or invoked with a passport argument.")

"""Django management entry point for the PRONTO report web adapter."""

import os
import sys


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pronto_web.settings")
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        os.environ.setdefault("PRONTO_DJANGO_SECRET_KEY", "test-only-not-for-deployment")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)

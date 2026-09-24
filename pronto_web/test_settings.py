"""Isolated defaults used only by pytest-django tests."""

import os

os.environ.setdefault("PRONTO_DJANGO_SECRET_KEY", "synthetic-test-only-not-for-deployment")

from .settings import *

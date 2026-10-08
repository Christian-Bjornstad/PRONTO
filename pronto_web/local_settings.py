"""Explicit local HTTP settings. The launcher binds exclusively to loopback."""
from .settings import *

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
PRONTO_DEMO_ENABLED = False
PRONTO_REQUIRE_INITIALS = False

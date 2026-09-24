"""Minimal, fail-closed Django settings for the read-only report slice."""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY = os.environ.get("PRONTO_DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("Set PRONTO_DJANGO_SECRET_KEY before starting the web app")

DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "pronto_web.reports",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "pronto_web.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "pronto_web" / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
    ]},
}]
LOGIN_REDIRECT_URL = "/reports/"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": os.environ.get("PRONTO_DJANGO_DB", str(BASE_DIR / "pronto_web.sqlite3")),
}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
# https://docs.djangoproject.com/en/5.2/howto/static-files/deployment/
STATICFILES_DIRS = [BASE_DIR / "pronto_report" / "static"]
STATIC_ROOT = os.environ.get("PRONTO_STATIC_ROOT", str(BASE_DIR / "collected-static"))
PRONTO_ALIGNMENT_SOURCE_ROOT = os.environ.get("PRONTO_ALIGNMENT_SOURCE_ROOT", "")
PRONTO_ALIGNMENT_REGISTRY_JSON = os.environ.get("PRONTO_ALIGNMENT_REGISTRY_JSON", "")
PRONTO_ALIGNMENT_STORE_ROOT = os.environ.get("PRONTO_ALIGNMENT_STORE_ROOT", "")
PRONTO_ALIGNMENT_STAGING_ROOT = os.environ.get("PRONTO_ALIGNMENT_STAGING_ROOT", "")
PRONTO_ALIGNMENT_POLICY_APPROVED = os.environ.get("PRONTO_ALIGNMENT_POLICY_APPROVED", "").lower() == "true"
PRONTO_ALIGNMENT_MAX_BYTES = int(os.environ.get("PRONTO_ALIGNMENT_MAX_BYTES", "0"))
PRONTO_ALIGNMENT_MAX_INDEX_BYTES = int(os.environ.get("PRONTO_ALIGNMENT_MAX_INDEX_BYTES", "0"))
PRONTO_ALIGNMENT_MAX_REPORT_BYTES = int(os.environ.get("PRONTO_ALIGNMENT_MAX_REPORT_BYTES", "0"))
PRONTO_ALIGNMENT_MIN_FREE_BYTES = int(os.environ.get("PRONTO_ALIGNMENT_MIN_FREE_BYTES", "0"))
PRONTO_ALIGNMENT_REFERENCE_FILES = {
    build: {"fasta": fasta, "index": index}
    for build in ("GRCh37", "GRCh38")
    if (fasta := os.environ.get(f"PRONTO_ALIGNMENT_{build}_FASTA_PATH", ""))
    and (index := os.environ.get(f"PRONTO_ALIGNMENT_{build}_FAI_PATH", ""))
}
PRONTO_IGV_REFERENCES = {
    build: {"fastaURL": os.environ.get(f"PRONTO_IGV_{build}_FASTA_URL", ""),
            "indexURL": os.environ.get(f"PRONTO_IGV_{build}_FAI_URL", "")}
    for build in ("GRCh37", "GRCh38")
}
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

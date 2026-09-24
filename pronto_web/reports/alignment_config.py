"""Fail-closed deployment gate for retaining sensitive alignment pairs."""

from pathlib import Path
import platform
import shutil


def _supported_platform() -> bool:
    # The pinned pysam wheel is distributed for Linux/macOS, not native Windows.
    return platform.system() == "Linux"


def alignment_saving_enabled(config) -> bool:
    """Only an explicitly approved, private Linux deployment may save pairs."""
    if not _supported_platform() or config.PRONTO_ALIGNMENT_POLICY_APPROVED is not True:
        return False
    if (config.PRONTO_ALIGNMENT_MAX_BYTES <= 0 or config.PRONTO_ALIGNMENT_MAX_INDEX_BYTES <= 0
            or config.PRONTO_ALIGNMENT_MAX_REPORT_BYTES <= 0):
        return False
    if config.PRONTO_ALIGNMENT_MIN_FREE_BYTES < 0:
        return False
    root_values = (config.PRONTO_ALIGNMENT_STORE_ROOT, config.PRONTO_ALIGNMENT_STAGING_ROOT)
    if not all(root_values):
        return False
    try:
        roots = tuple(Path(value).resolve(strict=True) for value in root_values)
        project_root = Path(config.BASE_DIR).resolve(strict=True)
        public_roots = [Path(config.STATIC_ROOT).resolve()] if config.STATIC_ROOT else []
        media_root = getattr(config, "MEDIA_ROOT", None)
        if media_root:
            public_roots.append(Path(media_root).resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    if (roots[0] == roots[1] or not all(root.is_dir() for root in roots)
            or any(root == project_root or project_root in root.parents for root in roots)
            or any(root == public or public in root.parents or root in public.parents
                   for root in roots for public in public_roots)):
        return False
    try:
        if any(shutil.disk_usage(root).free < config.PRONTO_ALIGNMENT_MIN_FREE_BYTES
               for root in roots):
            return False
    except OSError:
        return False
    references = config.PRONTO_ALIGNMENT_REFERENCE_FILES
    if not isinstance(references, dict):
        return False
    for build, pair in references.items():
        if build not in {"GRCh37", "GRCh38"} or not isinstance(pair, dict) or set(pair) != {"fasta", "index"}:
            return False
        try:
            if not all(Path(path).resolve(strict=True).is_file() for path in pair.values()):
                return False
        except (OSError, RuntimeError, ValueError):
            return False
    return bool(references)

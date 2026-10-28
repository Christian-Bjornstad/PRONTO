"""Keep local data private; Windows network folders inherit the area's team ACL."""
import os
from pathlib import Path


def create_data_directory(path, *, parents=True, exist_ok=True):
    path = Path(path)
    network = os.name == 'nt' and path.resolve().anchor.startswith('\\\\')
    # Since Python 3.13, 0700 applies an owner/admin-only DACL on Windows.
    # Other modes use normal inheritance; 0777 does not grant Everyone on Windows.
    path.mkdir(parents=parents, exist_ok=exist_ok, mode=0o777 if network else 0o700)

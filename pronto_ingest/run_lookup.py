"""Bounded directory-only lookup; return exact run groups before reading samples."""
from collections import deque
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
import stat

from .contracts import check_cancel
from .naming import classify_run_directory

MAX_DEPTH=3
MAX_ENTRIES=20000


@dataclass(frozen=True)
class RunLocation:
    run_id: str
    folders: tuple[Path,...]


def run_query(value):
    text=str(value).strip()
    if re.fullmatch(r'\d{6}_[A-Za-z0-9]+_\d{4}_[A-Za-z0-9]+',text):
        datetime.strptime(text[:6],'%y%m%d')
        return text
    formats={6:'%y%m%d',8:'%Y%m%d',10:'%Y-%m-%d'}
    try:
        pattern=formats[len(text)]
        if not re.fullmatch(r'\d{6}|\d{8}|\d{4}-\d{2}-\d{2}',text): raise ValueError()
        return datetime.strptime(text,pattern).strftime('%y%m%d')
    except (KeyError,ValueError):
        raise ValueError('Skriv kjøringsdato som 261021, 20261021 eller 2026-10-21, eller full kjørings-ID.') from None


def _safe_directory(path):
    info=path.lstat()
    return stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400


def find_runs(source_root, query, *, progress=None, cancel=None):
    query=run_query(query)
    root=Path(source_root).expanduser().absolute()
    # Reject links in the root's ancestors as in the normal import workflow.
    for part in (root,*root.parents):
        if not _safe_directory(part):
            raise ValueError('Velg en vanlig hovedmappe uten kataloglenker.')
    root=root.resolve(strict=True)
    queue=deque([(root,0)]);groups={};entries=0;denied=0;last_error=None
    while queue:
        check_cancel(cancel)
        folder,depth=queue.popleft()
        family=classify_run_directory(folder.name)
        if family:
            run,kind=family
            if run==query or run.startswith(query+'_'):
                groups.setdefault(run,{}).setdefault(kind,[]).append(folder)
            continue  # No sample traversal, even for other runs.
        if depth>=MAX_DEPTH:
            continue
        if progress and (depth==0 or entries%200==0):
            progress('Finner kjøringsmapper …')
        try:
            with os.scandir(folder) as children:
                for child in children:
                    check_cancel(cancel)
                    entries+=1
                    if entries>MAX_ENTRIES:
                        raise ValueError('Søkeområdet er for stort. Velg en hovedmappe nærmere kjøringsmappene.')
                    if child.name.startswith('.') or not child.is_dir(follow_symlinks=False):
                        continue
                    path=Path(child.path)
                    if _safe_directory(path): queue.append((path,depth+1))
        except PermissionError as error:
            denied+=1;last_error=error
    # Do not silently claim that a date is unique when part of the search was denied.
    if denied:
        raise ValueError(f'{denied} mapper kunne ikke leses. Velg et avgrenset søkeområde med lesetilgang. {last_error}')
    if not groups:
        raise ValueError('Fant ingen kjøring. Sjekk dato og hovedmappe. Søket går inntil tre mappenivåer ned.')
    found=[]
    for run,families in sorted(groups.items()):
        if any(len(paths)>1 for paths in families.values()):
            raise ValueError('Samme kjøring finnes flere steder. Velg en mer avgrenset hovedmappe eller bruk Mapper.')
        if 'raw' not in families:
            raise ValueError('Fant rapportmapper uten rådatamappen for kjøringen. Velg hovedmappen som også inneholder rådata.')
        folders=tuple(paths[0] for kind,paths in sorted(families.items()))
        if len(folders)>5:
            raise ValueError('Flere enn fem kjøringsmapper. Bruk Mapper og velg kildene eksplisitt.')
        found.append(RunLocation(run,folders))
    return tuple(found)

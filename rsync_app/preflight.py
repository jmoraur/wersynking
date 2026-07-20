"""Pure pre-flight checks for a binding about to run.

No I/O on Qt objects, no DB, no probes — the caller resolves the source
filesystem path, the destination context (mountpoint or network target),
and a single `available` bool (mounted for local, reachable for remote),
then this module returns a list of issues.

Issue shape: `{"severity": "error"|"warning", "code": str, "message": str}`.

Errors block the run unconditionally. Warnings block until the user
acknowledges each one in the dialog ("I understand").
"""
import os


def check_binding(row: dict, source: dict, dest: dict) -> list[dict]:
    """Inspect a binding draft + its resolved sides and return issues.

    `row` is the binding dict (path_mode, chown_*, opt_*, excludes, rsh,
    dest_subpath). `source` is `{"path": <abs source path>}`. `dest` is
    `{"kind": "local"|"remote", "base": <mountpoint|network_target>,
    "subpath": <dest_subpath>, "available": <bool>}`.
    """
    issues: list[dict] = []
    _check_source(source, issues)
    _check_dest(dest, issues)
    _check_warnings(row, source, dest, issues)
    return issues


def _err(code: str, message: str) -> dict:
    return {"severity": "error", "code": code, "message": message}


def _warn(code: str, message: str) -> dict:
    return {"severity": "warning", "code": code, "message": message}


def _check_source(source: dict, issues: list[dict]) -> None:
    path = (source or {}).get("path") or ""
    if not path:
        issues.append(_err("E_SRC_MISSING", "Source path is not set."))
        return
    if not os.path.isdir(path):
        issues.append(_err(
            "E_SRC_MISSING",
            f"Source path does not exist: {path}",
        ))
        return
    if not os.access(path, os.R_OK):
        issues.append(_err(
            "E_SRC_UNREADABLE",
            f"Source path is not readable: {path}",
        ))


def _check_dest(dest: dict, issues: list[dict]) -> None:
    kind = (dest or {}).get("kind", "")
    available = bool((dest or {}).get("available"))
    if kind == "local":
        if not available:
            issues.append(_err(
                "E_DEST_NOT_MOUNTED",
                "Destination device is not mounted.",
            ))
            return
        resolved = _resolved_dest_path(dest)
        ancestor = _existing_ancestor(resolved)
        if ancestor is None:
            issues.append(_err(
                "E_DEST_PARENT_UNWRITABLE",
                f"No existing parent directory for destination: {resolved}",
            ))
            return
        if not os.access(ancestor, os.W_OK):
            issues.append(_err(
                "E_DEST_PARENT_UNWRITABLE",
                f"Destination directory is not writable: {ancestor}",
            ))
        return
    if kind == "remote":
        if not available:
            issues.append(_err(
                "E_REMOTE_UNREACHABLE",
                "Remote host did not respond on the SSH port.",
            ))


def _check_warnings(row: dict, source: dict, dest: dict,
                    issues: list[dict]) -> None:
    if row.get("opt_delete"):
        issues.append(_warn(
            "W_DELETE_ENABLED",
            "--delete is enabled. Files on the destination that are not on"
            " the source will be removed.",
        ))

    path_mode = row.get("path_mode") or "contents"
    if path_mode == "folder":
        issues.append(_warn(
            "W_PATH_MODE_FOLDER",
            "Path mode is 'folder' — the source directory will be nested"
            " inside the destination (no trailing slash).",
        ))

    src_path = (source or {}).get("path") or ""
    if path_mode == "contents" and src_path:
        src_leaf = os.path.basename(src_path.rstrip("/"))
        dest_sub = (row.get("dest_subpath") or "").strip("/")
        if dest_sub:
            dest_leaf = os.path.basename(dest_sub)
        else:
            dest_leaf = os.path.basename(
                ((dest or {}).get("base") or "").rstrip("/")
            )
        if src_leaf and dest_leaf and src_leaf.lower() != dest_leaf.lower():
            issues.append(_warn(
                "W_BASENAME_MISMATCH",
                f"Source folder '{src_leaf}' differs from destination"
                f" folder '{dest_leaf}'. Confirm this is intentional.",
            ))

    if row.get("chown_mode") == "dest":
        if not (row.get("chown_value") or "").strip():
            issues.append(_warn(
                "W_DEST_CHOWN_EMPTY",
                "Ownership mode is 'force dest values' but --chown is empty.",
            ))
        if not (row.get("chmod_value") or "").strip():
            issues.append(_warn(
                "W_DEST_CHMOD_EMPTY",
                "Ownership mode is 'force dest values' but --chmod is empty.",
            ))

    excludes = row.get("excludes") or ""
    for idx, raw in enumerate(excludes.splitlines(), start=1):
        if not raw.strip():
            continue
        if "\r" in raw:
            issues.append(_warn(
                "W_EXCLUDES_CRLF",
                f"Excludes line {idx} contains a carriage return — rsync"
                " will treat it as part of the pattern.",
            ))
            continue
        if raw[0].isspace():
            issues.append(_warn(
                "W_EXCLUDES_WHITESPACE",
                f"Excludes line {idx} starts with whitespace — rsync"
                " treats leading spaces as part of the pattern.",
            ))


def _resolved_dest_path(dest: dict) -> str:
    base = (dest.get("base") or "").rstrip("/")
    subpath = (dest.get("subpath") or "").strip("/")
    return f"{base}/{subpath}" if subpath else base


def _existing_ancestor(path: str) -> str | None:
    if not path:
        return None
    cur = path
    while cur and not os.path.exists(cur):
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
    return cur or None

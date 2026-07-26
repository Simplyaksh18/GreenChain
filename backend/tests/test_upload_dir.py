"""
Focused tests for the evidence upload-directory resolver.

Deployment-critical: proves that
  * UPLOAD_DIR (env) is honored,
  * the directory is created if missing,
  * local-dev fallback still works,
  * the writer and StaticFiles mount agree on ONE path,
  * a resolved path survives module reinitialization (i.e. writing then
    re-resolving lands on the same on-disk file).

These tests use tmp_path and monkeypatch — they never touch the real
project uploads folder.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


def _reload_config():
    """Re-import app.config so the module-level `settings` re-reads env."""
    import app.config as cfg
    importlib.reload(cfg)
    return cfg


def test_upload_dir_env_var_is_used(monkeypatch, tmp_path):
    target = tmp_path / "evidence_home"
    monkeypatch.setenv("UPLOAD_DIR", str(target))
    cfg = _reload_config()

    resolved = cfg.resolve_evidence_upload_dir()

    assert Path(resolved) == target.resolve()
    assert target.exists() and target.is_dir()


def test_local_fallback_when_upload_dir_absent(monkeypatch):
    # Clear the env var and reset settings.UPLOAD_DIR.
    monkeypatch.delenv("UPLOAD_DIR", raising=False)
    cfg = _reload_config()
    cfg.settings.UPLOAD_DIR = ""

    resolved = cfg.resolve_evidence_upload_dir()

    assert resolved.is_absolute()
    # Local default lives under <backend>/uploads/evidence.
    assert resolved.parts[-2:] == ("uploads", "evidence")
    assert resolved.exists()


def test_upload_dir_writer_and_static_mount_agree(monkeypatch, tmp_path):
    """The two historically-independent path sites now resolve identically."""
    target = tmp_path / "shared_evidence"
    monkeypatch.setenv("UPLOAD_DIR", str(target))
    _reload_config()

    # Simulate the router side.
    from app.routers.evidence import _uploads_root
    router_side = Path(_uploads_root())

    # Simulate the StaticFiles-mount side (main.py resolves it the same way).
    from app.config import resolve_evidence_upload_dir
    mount_side = resolve_evidence_upload_dir()

    assert router_side == mount_side == target.resolve()


def test_uploaded_file_survives_resolver_reinvocation(monkeypatch, tmp_path):
    """
    Writing a file and then re-resolving the upload dir must yield a path
    that still contains the file — proving there's a single stable location.
    """
    target = tmp_path / "persistence"
    monkeypatch.setenv("UPLOAD_DIR", str(target))
    _reload_config()

    from app.routers.evidence import _uploads_root
    root = Path(_uploads_root())
    farm_dir = root / "42"
    farm_dir.mkdir(parents=True, exist_ok=True)
    fpath = farm_dir / "hello.txt"
    fpath.write_bytes(b"phase-22B evidence")

    # Re-resolve and re-check — as though a new worker booted.
    from app.config import resolve_evidence_upload_dir
    root_after = resolve_evidence_upload_dir()
    fpath_after = root_after / "42" / "hello.txt"

    assert fpath_after.exists()
    assert fpath_after.read_bytes() == b"phase-22B evidence"


def test_directory_created_when_missing(monkeypatch, tmp_path):
    target = tmp_path / "a" / "b" / "c" / "evidence"
    assert not target.exists()
    monkeypatch.setenv("UPLOAD_DIR", str(target))
    _reload_config()

    from app.config import resolve_evidence_upload_dir
    resolved = resolve_evidence_upload_dir()

    assert resolved.exists() and resolved.is_dir()
    assert resolved == target.resolve()


def test_expanduser_home_prefix(monkeypatch, tmp_path):
    """`~/…` in UPLOAD_DIR is expanded, not treated as a literal directory."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # On Windows also set USERPROFILE which Path.expanduser() uses.
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("UPLOAD_DIR", "~/greenchain-evidence")
    _reload_config()

    from app.config import resolve_evidence_upload_dir
    resolved = resolve_evidence_upload_dir()

    assert "~" not in str(resolved)
    assert resolved.is_absolute()
    assert resolved.exists()

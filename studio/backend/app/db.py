"""SQLite persistence for assets, jobs and outputs.

One small hand-rolled layer instead of an ORM: the schema is four tables wide
and every query lives in this file, which keeps the security-relevant paths
(no client-supplied filesystem paths, ever) easy to audit.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS assets (
    id              TEXT PRIMARY KEY,
    kind            TEXT NOT NULL,
    original_name   TEXT NOT NULL,
    stored_name     TEXT NOT NULL,
    mime            TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL,
    width           INTEGER,
    height          INTEGER,
    duration_seconds REAL,
    has_audio       INTEGER,
    comfy_name      TEXT,
    created_at      TEXT NOT NULL
);

-- Additive, idempotent migration for existing databases. Keep source IDs even if
-- an original is deleted, so a guide never silently becomes its own source.
CREATE TABLE IF NOT EXISTS guide_provenance (
    asset_id TEXT PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    source_asset_id TEXT NOT NULL,
    fit TEXT NOT NULL CHECK (fit IN ('pad', 'crop')),
    start_seconds REAL NOT NULL,
    source_duration_seconds REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id               TEXT PRIMARY KEY,
    status           TEXT NOT NULL,
    mode             TEXT NOT NULL,
    method           TEXT NOT NULL,
    title            TEXT,
    prompt           TEXT NOT NULL,
    width            INTEGER NOT NULL,
    height           INTEGER NOT NULL,
    length           INTEGER NOT NULL,
    seed             INTEGER NOT NULL,
    steps            INTEGER NOT NULL,
    request_json     TEXT NOT NULL,
    workflow_json    TEXT NOT NULL,
    comfy_prompt_id  TEXT,
    comfy_client_id  TEXT,
    progress         REAL NOT NULL DEFAULT 0,
    stage            TEXT,
    queue_position   INTEGER,
    error            TEXT,
    hidden           INTEGER NOT NULL DEFAULT 0,
    estimate_seconds REAL,
    created_at       TEXT NOT NULL,
    started_at       TEXT,
    finished_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_prompt ON jobs(comfy_prompt_id);

CREATE TABLE IF NOT EXISTS outputs (
    id           TEXT PRIMARY KEY,
    job_id       TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL,
    filename     TEXT NOT NULL,
    stored_name  TEXT NOT NULL,
    size_bytes   INTEGER NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_outputs_job ON outputs(job_id);

CREATE TABLE IF NOT EXISTS job_events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id  TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    ts      TEXT NOT NULL,
    level   TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_job ON job_events(job_id, id);

CREATE TABLE IF NOT EXISTS director_analyses (
    cache_key   TEXT PRIMARY KEY,
    asset_id    TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    model       TEXT NOT NULL,
    summary     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_director_asset ON director_analyses(asset_id);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cursor = self._conn.cursor()
            try:
                yield cursor
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cursor.close()

    # --- assets ----------------------------------------------------------
    def insert_asset(self, record: dict[str, Any]) -> None:
        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO assets (id, kind, original_name, stored_name, mime, size_bytes,
                                    width, height, duration_seconds, has_audio, comfy_name, created_at)
                VALUES (:id, :kind, :original_name, :stored_name, :mime, :size_bytes,
                        :width, :height, :duration_seconds, :has_audio, :comfy_name, :created_at)
                """,
                record,
            )

    def get_guide_provenance(self, asset_id: str) -> dict[str, Any] | None:
        with self._cursor() as cursor:
            row = cursor.execute('SELECT source_asset_id, fit, start_seconds, source_duration_seconds FROM guide_provenance WHERE asset_id=?', (asset_id,)).fetchone()
        return dict(row) if row else None

    def insert_guide_provenance(self, asset_id: str, source_asset_id: str, fit: str, start_seconds: float, source_duration_seconds: float) -> None:
        with self._cursor() as cursor:
            cursor.execute('INSERT INTO guide_provenance VALUES (?, ?, ?, ?, ?)', (asset_id, source_asset_id, fit, start_seconds, source_duration_seconds))

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        with self._cursor() as cursor:
            row = cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        return dict(row) if row else None

    def get_assets(self, asset_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not asset_ids:
            return {}
        placeholders = ",".join("?" for _ in asset_ids)
        with self._cursor() as cursor:
            rows = cursor.execute(
                f"SELECT * FROM assets WHERE id IN ({placeholders})", tuple(asset_ids)
            ).fetchall()
        return {row["id"]: dict(row) for row in rows}

    def set_asset_comfy_name(self, asset_id: str, comfy_name: str) -> None:
        with self._cursor() as cursor:
            cursor.execute("UPDATE assets SET comfy_name = ? WHERE id = ?", (comfy_name, asset_id))

    def list_assets(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._cursor() as cursor:
            rows = cursor.execute(
                "SELECT * FROM assets ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_asset(self, asset_id: str) -> dict[str, Any] | None:
        asset = self.get_asset(asset_id)
        if asset is None:
            return None
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        return asset

    # --- AI Director analysis cache --------------------------------------
    def get_director_analysis(self, cache_key: str) -> dict[str, Any] | None:
        with self._cursor() as cursor:
            row = cursor.execute(
                "SELECT * FROM director_analyses WHERE cache_key = ?", (cache_key,)
            ).fetchone()
        return dict(row) if row else None

    def put_director_analysis(self, record: dict[str, Any]) -> None:
        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO director_analyses (cache_key, asset_id, role, model, summary, created_at)
                VALUES (:cache_key, :asset_id, :role, :model, :summary, :created_at)
                ON CONFLICT(cache_key) DO UPDATE SET
                    summary=excluded.summary, created_at=excluded.created_at
                """,
                record,
            )

    # --- jobs ------------------------------------------------------------
    def insert_job(self, record: dict[str, Any]) -> None:
        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO jobs (id, status, mode, method, title, prompt, width, height, length,
                                  seed, steps, request_json, workflow_json, comfy_prompt_id,
                                  comfy_client_id, progress, stage, queue_position, error, hidden,
                                  estimate_seconds, created_at, started_at, finished_at)
                VALUES (:id, :status, :mode, :method, :title, :prompt, :width, :height, :length,
                        :seed, :steps, :request_json, :workflow_json, :comfy_prompt_id,
                        :comfy_client_id, :progress, :stage, :queue_position, :error, :hidden,
                        :estimate_seconds, :created_at, :started_at, :finished_at)
                """,
                record,
            )

    def update_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        allowed = {
            "status",
            "comfy_prompt_id",
            "comfy_client_id",
            "progress",
            "stage",
            "queue_position",
            "error",
            "hidden",
            "started_at",
            "finished_at",
            "title",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Refusing to update unknown job columns: {sorted(unknown)}")
        assignments = ", ".join(f"{key} = :{key}" for key in fields)
        params = dict(fields)
        params["job_id"] = job_id
        with self._cursor() as cursor:
            cursor.execute(f"UPDATE jobs SET {assignments} WHERE id = :job_id", params)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._cursor() as cursor:
            row = cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def get_job_by_prompt_id(self, prompt_id: str) -> dict[str, Any] | None:
        with self._cursor() as cursor:
            row = cursor.execute("SELECT * FROM jobs WHERE comfy_prompt_id = ?", (prompt_id,)).fetchone()
        return dict(row) if row else None

    def list_jobs(
        self,
        *,
        include_hidden: bool = False,
        statuses: list[str] | None = None,
        limit: int = 60,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if not include_hidden:
            clauses.append("hidden = 0")
        if statuses:
            clauses.append(f"status IN ({','.join('?' for _ in statuses)})")
            params.extend(statuses)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._cursor() as cursor:
            total = cursor.execute(f"SELECT COUNT(*) AS c FROM jobs {where}", tuple(params)).fetchone()["c"]
            rows = cursor.execute(
                f"SELECT * FROM jobs {where} ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [dict(row) for row in rows], int(total)

    def active_jobs(self) -> list[dict[str, Any]]:
        with self._cursor() as cursor:
            rows = cursor.execute(
                "SELECT * FROM jobs WHERE status IN ('queued','running') ORDER BY created_at ASC"
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_job(self, job_id: str) -> list[dict[str, Any]]:
        outputs = self.list_outputs(job_id)
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM job_events WHERE job_id = ?", (job_id,))
            cursor.execute("DELETE FROM outputs WHERE job_id = ?", (job_id,))
            cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return outputs

    # --- job events (secondary log stream) --------------------------------
    def add_event(self, job_id: str, level: str, message: str) -> None:
        with self._cursor() as cursor:
            cursor.execute(
                "INSERT INTO job_events (job_id, ts, level, message) VALUES (?, ?, ?, ?)",
                (job_id, utcnow(), level, message[:2000]),
            )

    def list_events(self, job_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._cursor() as cursor:
            rows = cursor.execute(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY id ASC LIMIT ?", (job_id, limit)
            ).fetchall()
        return [dict(row) for row in rows]

    # --- outputs ---------------------------------------------------------
    def insert_output(self, record: dict[str, Any]) -> None:
        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO outputs (id, job_id, kind, filename, stored_name, size_bytes, created_at)
                VALUES (:id, :job_id, :kind, :filename, :stored_name, :size_bytes, :created_at)
                """,
                record,
            )

    def list_outputs(self, job_id: str) -> list[dict[str, Any]]:
        with self._cursor() as cursor:
            rows = cursor.execute(
                "SELECT * FROM outputs WHERE job_id = ? ORDER BY created_at ASC", (job_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_output(self, output_id: str) -> dict[str, Any] | None:
        with self._cursor() as cursor:
            row = cursor.execute("SELECT * FROM outputs WHERE id = ?", (output_id,)).fetchone()
        return dict(row) if row else None

    def outputs_for_jobs(self, job_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not job_ids:
            return {}
        placeholders = ",".join("?" for _ in job_ids)
        with self._cursor() as cursor:
            rows = cursor.execute(
                f"SELECT * FROM outputs WHERE job_id IN ({placeholders}) ORDER BY created_at ASC",
                tuple(job_ids),
            ).fetchall()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["job_id"], []).append(dict(row))
        return grouped


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def loads(value: str | None) -> Any:
    if not value:
        return None
    return json.loads(value)

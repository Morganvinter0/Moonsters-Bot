from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from config import ETAPA_ORDEM

DB_PATH = Path(__file__).parent / "data" / "scan.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self.db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(self.path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA foreign_keys = ON")
        await self.db.execute("PRAGMA journal_mode = WAL")
        await self._create_tables()

    async def close(self) -> None:
        if self.db:
            await self.db.close()
            self.db = None

    async def _create_tables(self) -> None:
        assert self.db
        await self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS obras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                sigla TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ativa',
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(guild_id, sigla)
            );

            CREATE TABLE IF NOT EXISTS capitulos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                obra_id INTEGER NOT NULL,
                numero TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'aberto',
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                closed_at TEXT,
                UNIQUE(obra_id, numero),
                FOREIGN KEY(obra_id) REFERENCES obras(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS etapas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capitulo_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                UNIQUE(capitulo_id, tipo),
                FOREIGN KEY(capitulo_id) REFERENCES capitulos(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_obras_guild ON obras(guild_id);
            CREATE INDEX IF NOT EXISTS idx_caps_obra ON capitulos(obra_id, status);
            CREATE INDEX IF NOT EXISTS idx_etapas_user ON etapas(user_id);

            CREATE TABLE IF NOT EXISTS equipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(guild_id, nome)
            );

            CREATE TABLE IF NOT EXISTS equipe_membros (
                equipe_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                added_at TEXT NOT NULL,
                PRIMARY KEY(equipe_id, user_id),
                FOREIGN KEY(equipe_id) REFERENCES equipes(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_equipes_guild ON equipes(guild_id);
            CREATE INDEX IF NOT EXISTS idx_equipe_membros_user ON equipe_membros(user_id);
            """
        )
        await self.db.commit()

    # ── obras ──────────────────────────────────────────────
    async def add_obra(
        self, guild_id: int, nome: str, sigla: str, created_by: int
    ) -> dict[str, Any]:
        assert self.db
        sigla = sigla.upper().strip()
        nome = nome.strip()
        cur = await self.db.execute(
            """
            INSERT INTO obras (guild_id, nome, sigla, created_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, nome, sigla, created_by, _now()),
        )
        await self.db.commit()
        return {
            "id": cur.lastrowid,
            "guild_id": guild_id,
            "nome": nome,
            "sigla": sigla,
            "status": "ativa",
        }

    async def get_obra(self, guild_id: int, query: str) -> Optional[aiosqlite.Row]:
        assert self.db
        q = query.strip()
        cur = await self.db.execute(
            """
            SELECT * FROM obras
            WHERE guild_id = ?
              AND (UPPER(sigla) = UPPER(?) OR LOWER(nome) = LOWER(?))
            """,
            (guild_id, q, q),
        )
        row = await cur.fetchone()
        if row:
            return row
        cur = await self.db.execute(
            """
            SELECT * FROM obras
            WHERE guild_id = ?
              AND (UPPER(sigla) LIKE UPPER(?) OR LOWER(nome) LIKE LOWER(?))
            ORDER BY LENGTH(nome) ASC
            LIMIT 1
            """,
            (guild_id, f"%{q}%", f"%{q}%"),
        )
        return await cur.fetchone()

    async def list_obras(self, guild_id: int, status: Optional[str] = None) -> list[aiosqlite.Row]:
        assert self.db
        if status:
            cur = await self.db.execute(
                "SELECT * FROM obras WHERE guild_id = ? AND status = ? ORDER BY nome",
                (guild_id, status),
            )
        else:
            cur = await self.db.execute(
                "SELECT * FROM obras WHERE guild_id = ? ORDER BY status, nome",
                (guild_id,),
            )
        return await cur.fetchall()

    async def search_obras(self, guild_id: int, query: str, limit: int = 25) -> list[aiosqlite.Row]:
        assert self.db
        cur = await self.db.execute(
            """
            SELECT * FROM obras
            WHERE guild_id = ? AND status = 'ativa'
              AND (UPPER(sigla) LIKE UPPER(?) OR LOWER(nome) LIKE LOWER(?))
            ORDER BY nome
            LIMIT ?
            """,
            (guild_id, f"%{query}%", f"%{query}%", limit),
        )
        return await cur.fetchall()

    async def set_obra_status(self, obra_id: int, status: str) -> None:
        assert self.db
        await self.db.execute("UPDATE obras SET status = ? WHERE id = ?", (status, obra_id))
        await self.db.commit()

    async def delete_obra(self, obra_id: int) -> None:
        assert self.db
        await self.db.execute("DELETE FROM obras WHERE id = ?", (obra_id,))
        await self.db.commit()

    # ── capítulos ──────────────────────────────────────────
    async def get_or_create_cap(
        self, obra_id: int, numero: str, created_by: int
    ) -> tuple[aiosqlite.Row, bool]:
        assert self.db
        numero = str(numero).strip()
        cur = await self.db.execute(
            "SELECT * FROM capitulos WHERE obra_id = ? AND numero = ?",
            (obra_id, numero),
        )
        row = await cur.fetchone()
        if row:
            return row, False
        cur = await self.db.execute(
            """
            INSERT INTO capitulos (obra_id, numero, created_by, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (obra_id, numero, created_by, _now()),
        )
        await self.db.commit()
        cur = await self.db.execute("SELECT * FROM capitulos WHERE id = ?", (cur.lastrowid,))
        return await cur.fetchone(), True

    async def get_cap(self, obra_id: int, numero: str) -> Optional[aiosqlite.Row]:
        assert self.db
        cur = await self.db.execute(
            "SELECT * FROM capitulos WHERE obra_id = ? AND numero = ?",
            (obra_id, str(numero).strip()),
        )
        return await cur.fetchone()

    async def list_caps(self, obra_id: int, status: Optional[str] = None) -> list[aiosqlite.Row]:
        assert self.db
        if status:
            cur = await self.db.execute(
                """
                SELECT * FROM capitulos
                WHERE obra_id = ? AND status = ?
                ORDER BY CAST(numero AS REAL), numero
                """,
                (obra_id, status),
            )
        else:
            cur = await self.db.execute(
                """
                SELECT * FROM capitulos
                WHERE obra_id = ?
                ORDER BY status ASC, CAST(numero AS REAL), numero
                """,
                (obra_id,),
            )
        return await cur.fetchall()

    async def list_caps_abertos_guild(self, guild_id: int) -> list[aiosqlite.Row]:
        assert self.db
        cur = await self.db.execute(
            """
            SELECT c.*, o.nome AS obra_nome, o.sigla AS obra_sigla
            FROM capitulos c
            JOIN obras o ON o.id = c.obra_id
            WHERE o.guild_id = ? AND c.status = 'aberto'
            ORDER BY o.nome, CAST(c.numero AS REAL), c.numero
            """,
            (guild_id,),
        )
        return await cur.fetchall()

    async def fechar_cap(self, cap_id: int) -> None:
        assert self.db
        await self.db.execute(
            "UPDATE capitulos SET status = 'fechado', closed_at = ? WHERE id = ?",
            (_now(), cap_id),
        )
        await self.db.commit()

    async def reabrir_cap(self, cap_id: int) -> None:
        assert self.db
        await self.db.execute(
            "UPDATE capitulos SET status = 'aberto', closed_at = NULL WHERE id = ?",
            (cap_id,),
        )
        await self.db.commit()

    # ── etapas ─────────────────────────────────────────────
    async def set_etapa(
        self, cap_id: int, tipo: str, user_id: int, user_name: str
    ) -> tuple[str, Optional[aiosqlite.Row]]:
        """Define ou troca o responsável da etapa. Retorna ('nova'|'trocada', etapa_anterior)."""
        assert self.db
        cur = await self.db.execute(
            "SELECT * FROM etapas WHERE capitulo_id = ? AND tipo = ?",
            (cap_id, tipo),
        )
        antiga = await cur.fetchone()
        if antiga:
            await self.db.execute(
                """
                UPDATE etapas
                SET user_id = ?, user_name = ?, completed_at = ?
                WHERE capitulo_id = ? AND tipo = ?
                """,
                (user_id, user_name, _now(), cap_id, tipo),
            )
            await self.db.commit()
            return "trocada", antiga
        await self.db.execute(
            """
            INSERT INTO etapas (capitulo_id, tipo, user_id, user_name, completed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (cap_id, tipo, user_id, user_name, _now()),
        )
        await self.db.commit()
        return "nova", None

    async def unset_etapa(self, cap_id: int, tipo: str) -> Optional[aiosqlite.Row]:
        assert self.db
        cur = await self.db.execute(
            "SELECT * FROM etapas WHERE capitulo_id = ? AND tipo = ?",
            (cap_id, tipo),
        )
        row = await cur.fetchone()
        if not row:
            return None
        await self.db.execute(
            "DELETE FROM etapas WHERE capitulo_id = ? AND tipo = ?",
            (cap_id, tipo),
        )
        await self.db.commit()
        return row

    async def get_etapas(self, cap_id: int) -> dict[str, aiosqlite.Row]:
        assert self.db
        cur = await self.db.execute(
            "SELECT * FROM etapas WHERE capitulo_id = ?",
            (cap_id,),
        )
        rows = await cur.fetchall()
        return {r["tipo"]: r for r in rows}

    async def etapas_completas(self, cap_id: int) -> bool:
        etapas = await self.get_etapas(cap_id)
        return all(sigla in etapas for sigla in ETAPA_ORDEM)

    async def progresso_caps(self, cap_ids: list[int]) -> dict[int, int]:
        """Quantas etapas cada capítulo já tem."""
        if not cap_ids:
            return {}
        assert self.db
        placeholders = ",".join("?" * len(cap_ids))
        cur = await self.db.execute(
            f"""
            SELECT capitulo_id, COUNT(*) AS n
            FROM etapas
            WHERE capitulo_id IN ({placeholders})
            GROUP BY capitulo_id
            """,
            cap_ids,
        )
        rows = await cur.fetchall()
        return {r["capitulo_id"]: r["n"] for r in rows}

    # ── ranking ────────────────────────────────────────────
    async def ranking(
        self, guild_id: int, since: Optional[str] = None, limit: int = 15
    ) -> list[aiosqlite.Row]:
        assert self.db
        if since:
            cur = await self.db.execute(
                """
                SELECT e.user_id, e.user_name, COUNT(*) AS total
                FROM etapas e
                JOIN capitulos c ON c.id = e.capitulo_id
                JOIN obras o ON o.id = c.obra_id
                WHERE o.guild_id = ? AND e.completed_at >= ?
                GROUP BY e.user_id
                ORDER BY total DESC, e.user_name ASC
                LIMIT ?
                """,
                (guild_id, since, limit),
            )
        else:
            cur = await self.db.execute(
                """
                SELECT e.user_id, e.user_name, COUNT(*) AS total
                FROM etapas e
                JOIN capitulos c ON c.id = e.capitulo_id
                JOIN obras o ON o.id = c.obra_id
                WHERE o.guild_id = ?
                GROUP BY e.user_id
                ORDER BY total DESC, e.user_name ASC
                LIMIT ?
                """,
                (guild_id, limit),
            )
        return await cur.fetchall()

    async def ranking_por_etapa(
        self, guild_id: int, tipo: str, limit: int = 10
    ) -> list[aiosqlite.Row]:
        assert self.db
        cur = await self.db.execute(
            """
            SELECT e.user_id, e.user_name, COUNT(*) AS total
            FROM etapas e
            JOIN capitulos c ON c.id = e.capitulo_id
            JOIN obras o ON o.id = c.obra_id
            WHERE o.guild_id = ? AND e.tipo = ?
            GROUP BY e.user_id
            ORDER BY total DESC
            LIMIT ?
            """,
            (guild_id, tipo, limit),
        )
        return await cur.fetchall()


    # ── equipes / dashboards ─────────────────────────────
    async def add_equipe(self, guild_id: int, nome: str, created_by: int) -> dict[str, Any]:
        assert self.db
        cur = await self.db.execute(
            "INSERT INTO equipes (guild_id, nome, created_by, created_at) VALUES (?, ?, ?, ?)",
            (guild_id, nome.strip(), created_by, _now()),
        )
        await self.db.commit()
        return {"id": cur.lastrowid, "guild_id": guild_id, "nome": nome.strip()}

    async def get_equipe(self, guild_id: int, nome: str):
        assert self.db
        cur = await self.db.execute(
            "SELECT * FROM equipes WHERE guild_id = ? AND LOWER(nome) = LOWER(?)",
            (guild_id, nome.strip()),
        )
        row = await cur.fetchone()
        if row: return row
        cur = await self.db.execute(
            "SELECT * FROM equipes WHERE guild_id = ? AND LOWER(nome) LIKE LOWER(?) ORDER BY nome LIMIT 1",
            (guild_id, f"%{nome.strip()}%"),
        )
        return await cur.fetchone()

    async def list_equipes(self, guild_id: int):
        assert self.db
        cur = await self.db.execute("SELECT * FROM equipes WHERE guild_id = ? ORDER BY nome", (guild_id,))
        return await cur.fetchall()

    async def add_membro_equipe(self, equipe_id: int, user_id: int, user_name: str) -> None:
        assert self.db
        await self.db.execute(
            "INSERT OR REPLACE INTO equipe_membros (equipe_id,user_id,user_name,added_at) VALUES (?,?,?,?)",
            (equipe_id, user_id, user_name, _now()),
        )
        await self.db.commit()

    async def membros_equipe(self, equipe_id: int):
        assert self.db
        cur = await self.db.execute("SELECT * FROM equipe_membros WHERE equipe_id = ? ORDER BY user_name", (equipe_id,))
        return await cur.fetchall()

    async def stats_equipe(self, equipe_id: int, since: str | None = None):
        assert self.db
        if since:
            q = """SELECT e.user_id,e.user_name,COUNT(*) total FROM equipe_membros m JOIN etapas e ON e.user_id=m.user_id JOIN capitulos c ON c.id=e.capitulo_id JOIN obras o ON o.id=c.obra_id WHERE m.equipe_id=? AND o.guild_id=(SELECT guild_id FROM equipes WHERE id=?) AND e.completed_at>=? GROUP BY e.user_id ORDER BY total DESC"""
            args=(equipe_id,equipe_id,since)
        else:
            q = """SELECT e.user_id,e.user_name,COUNT(*) total FROM equipe_membros m JOIN etapas e ON e.user_id=m.user_id JOIN capitulos c ON c.id=e.capitulo_id JOIN obras o ON o.id=c.obra_id WHERE m.equipe_id=? AND o.guild_id=(SELECT guild_id FROM equipes WHERE id=?) GROUP BY e.user_id ORDER BY total DESC"""
            args=(equipe_id,equipe_id)
        cur=await self.db.execute(q,args); return await cur.fetchall()

    async def user_stats(self, guild_id: int, user_id: int):
        assert self.db
        cur=await self.db.execute("""SELECT COUNT(*) total, COUNT(DISTINCT c.id) capitulos, COUNT(DISTINCT o.id) obras FROM etapas e JOIN capitulos c ON c.id=e.capitulo_id JOIN obras o ON o.id=c.obra_id WHERE o.guild_id=? AND e.user_id=?""",(guild_id,user_id)); return await cur.fetchone()

    async def user_etapas(self, guild_id: int, user_id: int):
        assert self.db
        cur=await self.db.execute("""SELECT e.tipo,COUNT(*) total FROM etapas e JOIN capitulos c ON c.id=e.capitulo_id JOIN obras o ON o.id=c.obra_id WHERE o.guild_id=? AND e.user_id=? GROUP BY e.tipo ORDER BY total DESC""",(guild_id,user_id)); return await cur.fetchall()

    async def dashboard_stats(self, guild_id: int):
        assert self.db
        cur=await self.db.execute("""SELECT COUNT(*) total_caps, SUM(CASE WHEN c.status='aberto' THEN 1 ELSE 0 END) abertos, SUM(CASE WHEN c.status='fechado' THEN 1 ELSE 0 END) fechados, COUNT(DISTINCT o.id) obras FROM capitulos c JOIN obras o ON o.id=c.obra_id WHERE o.guild_id=?""",(guild_id,)); return await cur.fetchone()

    async def etapas_periodo(self, guild_id: int, since: str):
        assert self.db
        cur=await self.db.execute("""SELECT COUNT(*) total FROM etapas e JOIN capitulos c ON c.id=e.capitulo_id JOIN obras o ON o.id=c.obra_id WHERE o.guild_id=? AND e.completed_at>=?""",(guild_id,since)); return (await cur.fetchone())["total"] or 0

    async def stats_obra(self, obra_id: int) -> dict[str, int]:
        assert self.db
        cur = await self.db.execute(
            """
            SELECT
              SUM(CASE WHEN status = 'aberto' THEN 1 ELSE 0 END) AS abertos,
              SUM(CASE WHEN status = 'fechado' THEN 1 ELSE 0 END) AS fechados,
              COUNT(*) AS total
            FROM capitulos
            WHERE obra_id = ?
            """,
            (obra_id,),
        )
        row = await cur.fetchone()
        return {
            "abertos": row["abertos"] or 0,
            "fechados": row["fechados"] or 0,
            "total": row["total"] or 0,
        }

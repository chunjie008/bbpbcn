# 版权所有 (c) 2018-2024 NCC Group Plc
#
# 特此免费授予任何获得本软件及相关文档文件（"软件"）副本的人，不受限制地处理
# 本软件的权利，包括但不限于使用、复制、修改、合并、发布、分发、再许可和/或
# 销售本软件副本的权利，并允许获得本软件的人这样做，但须符合以下条件：
#
# 上述版权声明和本许可声明应包含在本软件的所有副本或实质性部分中。
#
# 本软件按"原样"提供，不作任何明示或暗示的担保，包括但不限于对适销性、特定
# 用途适用性和非侵权的担保。在任何情况下，作者或版权持有人均不对因使用本软件
# 而产生的任何索赔、损害或其他责任承担责任，无论是合同行为、侵权行为还是其他
# 行为。

import os
import json
import sqlite3
import datetime


DB_DIR_NAME = ".bbpbcn"
DB_FILE_NAME = "bbpb.db"


def get_db_dir():
    # type: () -> str
    env_dir = os.environ.get("BBPB_CN_DB_DIR", "")
    if env_dir:
        return env_dir
    return os.path.join(os.getcwd(), DB_DIR_NAME)


def get_db_path():
    # type: () -> str
    return os.path.join(get_db_dir(), DB_FILE_NAME)


# 表结构和索引
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL DEFAULT '',
    msgid INTEGER NOT NULL DEFAULT 0,
    direction TEXT NOT NULL DEFAULT '',
    hex TEXT NOT NULL DEFAULT '',
    typedef TEXT NOT NULL DEFAULT '{}',
    describe TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS typedef_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    typedef TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    changed_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    msg_ids TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_messages_project ON messages(project);
CREATE INDEX IF NOT EXISTS idx_messages_msgid ON messages(msgid);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_messages_project_msgid ON messages(project, msgid);
"""


class BbpDB(object):
    """bbpbcn SQLite 数据库封装"""

    def __init__(self):
        # type: () -> None
        db_dir = get_db_dir()
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        self.db_path = get_db_path()
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def close(self):
        # type: () -> None
        self.conn.close()

    @staticmethod
    def _now():
        # type: () -> str
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── messages CRUD ──

    def insert_message(self, **kw):
        # type: (**str | int) -> int
        fields = {
            "project": "",
            "msgid": 0,
            "direction": "",
            "hex": "",
            "typedef": "{}",
            "describe": "",
            "remark": "",
            "status": "pending",
        }
        fields.update(kw)
        now = self._now()
        fields["created_at"] = now
        fields["updated_at"] = now
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        values = list(fields.values())
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO messages (%s) VALUES (%s)" % (cols, placeholders),
            values,
        )
        self.conn.commit()
        return c.lastrowid

    def get_message(self, id):
        # type: (int) -> sqlite3.Row | None
        c = self.conn.cursor()
        c.execute("SELECT * FROM messages WHERE id = ?", (id,))
        return c.fetchone()

    def update_message(self, id, **kw):
        # type: (int, **object) -> bool
        allowed = {
            "project", "msgid", "direction", "hex",
            "typedef", "describe", "remark", "status",
        }
        updates = {}
        for k, v in kw.items():
            if k in allowed and v is not None:
                updates[k] = v
        if not updates:
            return False
        updates["updated_at"] = self._now()
        set_clause = ", ".join("%s = ?" % k for k in updates)
        values = list(updates.values()) + [id]
        c = self.conn.cursor()
        c.execute("UPDATE messages SET %s WHERE id = ?" % set_clause, values)
        self.conn.commit()

        if "typedef" in updates:
            row = c.execute(
                "SELECT COUNT(*) FROM typedef_history WHERE message_id = ?",
                (id,),
            ).fetchone()
            version = (row[0] if row else 0) + 1
            c.execute(
                "INSERT INTO typedef_history (message_id, typedef, version, changed_at) "
                "VALUES (?, ?, ?, ?)",
                (id, updates["typedef"], version, updates["updated_at"]),
            )
            self.conn.commit()

        return c.rowcount > 0

    def delete_message(self, id):
        # type: (int) -> bool
        c = self.conn.cursor()
        c.execute("DELETE FROM typedef_history WHERE message_id = ?", (id,))
        c.execute("DELETE FROM messages WHERE id = ?", (id,))
        self.conn.commit()
        return c.rowcount > 0

    # ── query ──

    def list_messages(self, project=None, status=None, msgid=None, limit=50, offset=0):
        # type: (str | None, str | None, int | None, int, int) -> list[sqlite3.Row]
        conds = []
        vals = []
        if project:
            conds.append("project = ?")
            vals.append(project)
        if status:
            conds.append("status = ?")
            vals.append(status)
        if msgid is not None:
            conds.append("msgid = ?")
            vals.append(msgid)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        c = self.conn.cursor()
        c.execute(
            "SELECT * FROM messages%s ORDER BY updated_at DESC LIMIT ? OFFSET ?" % where,
            vals + [limit, offset],
        )
        return c.fetchall()

    def search_messages(self, keyword, project=None):
        # type: (str, str | None) -> list[sqlite3.Row]
        conds = []
        vals = []
        like = "%%%s%%" % keyword
        if project:
            conds.append("project = ?")
            vals.append(project)
        conds.append(
            "(project LIKE ? OR describe LIKE ? OR remark LIKE ? "
            "OR hex LIKE ? OR msgid LIKE ? OR direction LIKE ?)"
        )
        vals.extend([like] * 6)
        where = " WHERE " + " AND ".join(conds)
        c = self.conn.cursor()
        c.execute("SELECT * FROM messages%s ORDER BY updated_at DESC" % where, vals)
        return c.fetchall()

    # ── stats ──

    def stats(self, project=None):
        # type: (str | None) -> dict
        c = self.conn.cursor()
        if project:
            total = c.execute(
                "SELECT COUNT(*) FROM messages WHERE project = ?", (project,)
            ).fetchone()[0]
            by_msgid = c.execute(
                "SELECT msgid, COUNT(*) as cnt FROM messages "
                "WHERE project = ? GROUP BY msgid ORDER BY cnt DESC",
                (project,),
            ).fetchall()
            by_status = c.execute(
                "SELECT status, COUNT(*) as cnt FROM messages "
                "WHERE project = ? GROUP BY status",
                (project,),
            ).fetchall()
            by_direction = c.execute(
                "SELECT direction, COUNT(*) as cnt FROM messages "
                "WHERE project = ? GROUP BY direction",
                (project,),
            ).fetchall()
        else:
            total = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            by_msgid = c.execute(
                "SELECT msgid, COUNT(*) as cnt FROM messages "
                "GROUP BY msgid ORDER BY cnt DESC"
            ).fetchall()
            by_status = c.execute(
                "SELECT status, COUNT(*) as cnt FROM messages GROUP BY status"
            ).fetchall()
            by_direction = c.execute(
                "SELECT direction, COUNT(*) as cnt FROM messages GROUP BY direction"
            ).fetchall()
        return {
            "total": total,
            "by_msgid": [
                {"msgid": r[0], "count": r[1]} for r in by_msgid
            ],
            "by_status": [
                {"status": r[0], "count": r[1]} for r in by_status
            ],
            "by_direction": [
                {"direction": r[0], "count": r[1]} for r in by_direction
            ],
        }

    # ── typedef_history ──

    def get_history(self, message_id):
        # type: (int) -> list[sqlite3.Row]
        c = self.conn.cursor()
        c.execute(
            "SELECT * FROM typedef_history WHERE message_id = ? ORDER BY version ASC",
            (message_id,),
        )
        return c.fetchall()

    # ── sessions ──

    def create_session(self, project="", name="", msg_ids=None, notes=""):
        # type: (str, str, list[int] | None, str) -> int
        now = self._now()
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO sessions (project, name, msg_ids, notes, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (project, name, json.dumps(msg_ids or []), notes, now),
        )
        self.conn.commit()
        return c.lastrowid

    def get_session(self, id):
        # type: (int) -> sqlite3.Row | None
        c = self.conn.cursor()
        c.execute("SELECT * FROM sessions WHERE id = ?", (id,))
        return c.fetchone()

    def list_sessions(self, project=None):
        # type: (str | None) -> list[sqlite3.Row]
        c = self.conn.cursor()
        if project:
            c.execute(
                "SELECT * FROM sessions WHERE project = ? ORDER BY created_at DESC",
                (project,),
            )
        else:
            c.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        return c.fetchall()

    def delete_session(self, id):
        # type: (int) -> bool
        c = self.conn.cursor()
        c.execute("DELETE FROM sessions WHERE id = ?", (id,))
        self.conn.commit()
        return c.rowcount > 0

    # ── export ──

    def export_typedefs(self, project=None, message_ids=None):
        # type: (str | None, list[int] | None) -> dict
        c = self.conn.cursor()
        if message_ids:
            placeholders = ", ".join("?" for _ in message_ids)
            rows = c.execute(
                "SELECT id, msgid, project, typedef, describe FROM messages "
                "WHERE id IN (%s) ORDER BY msgid" % placeholders,
                message_ids,
            ).fetchall()
        elif project:
            rows = c.execute(
                "SELECT id, msgid, project, typedef, describe FROM messages "
                "WHERE project = ? ORDER BY msgid",
                (project,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id, msgid, project, typedef, describe FROM messages "
                "ORDER BY msgid"
            ).fetchall()
        result = {}
        for r in rows:
            name = "msg_%d_%s" % (r["msgid"], r["describe"] or "unknown")
            name = "".join(c if c.isalnum() and ord(c) < 128 or c == "_" else "_" for c in name)
            name = name.strip("_") or ("msg_%d" % r["msgid"])
            try:
                td = json.loads(r["typedef"]) if r["typedef"] else {}
                if td:
                    result[name] = td
            except (ValueError, TypeError):
                pass
        return result

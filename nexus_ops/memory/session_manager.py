"""Session Management for Multi-Turn Stateful Agent Interactions."""

from typing import Any, Dict, List, Optional
from datetime import datetime
import json
import sqlite3
from pydantic import BaseModel, Field
from nexus_ops.config import settings


class MessageTurn(BaseModel):
    role: str  # user, assistant, system, tool
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionState(BaseModel):
    session_id: str
    user_id: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    turns: List[MessageTurn] = Field(default_factory=list)
    active_order_id: Optional[str] = None
    customer_tier: Optional[str] = None
    variables: Dict[str, Any] = Field(default_factory=dict)


class SessionManager:
    """Manages multi-turn conversation sessions with persistent SQLite storage."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or (
            settings.database_url.replace("sqlite:///", "")
            if settings.database_url.startswith("sqlite:///")
            else ":memory:"
        )
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    active_order_id TEXT,
                    customer_tier TEXT,
                    variables_json TEXT NOT NULL,
                    turns_json TEXT NOT NULL
                )
            """)
            conn.commit()

    def get_or_create_session(self, session_id: str, user_id: str) -> SessionState:
        """Retrieves an existing session state or initializes a new one."""
        with self._get_conn() as conn:
            cur = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cur.fetchone()
            if row:
                turns_data = json.loads(row["turns_json"])
                vars_data = json.loads(row["variables_json"])
                return SessionState(
                    session_id=row["session_id"],
                    user_id=row["user_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    active_order_id=row["active_order_id"],
                    customer_tier=row["customer_tier"],
                    variables=vars_data,
                    turns=[MessageTurn(**t) for t in turns_data]
                )

        new_session = SessionState(session_id=session_id, user_id=user_id)
        self.save_session(new_session)
        return new_session

    def save_session(self, session: SessionState):
        """Persists the session state to database."""
        session.updated_at = datetime.utcnow().isoformat()
        turns_json = json.dumps([t.model_dump() for t in session.turns])
        vars_json = json.dumps(session.variables)

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO sessions (
                    session_id, user_id, created_at, updated_at,
                    active_order_id, customer_tier, variables_json, turns_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    updated_at=excluded.updated_at,
                    active_order_id=excluded.active_order_id,
                    customer_tier=excluded.customer_tier,
                    variables_json=excluded.variables_json,
                    turns_json=excluded.turns_json
            """, (
                session.session_id, session.user_id, session.created_at,
                session.updated_at, session.active_order_id, session.customer_tier,
                vars_json, turns_json
            ))
            conn.commit()

    def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MessageTurn:
        """Appends a new conversational turn and updates session."""
        with self._get_conn() as conn:
            cur = conn.execute("SELECT user_id FROM sessions WHERE session_id = ?", (session_id,))
            row = cur.fetchone()
            user_id = row["user_id"] if row else "default_user"

        session = self.get_or_create_session(session_id, user_id)
        turn = MessageTurn(role=role, content=content, metadata=metadata or {})
        session.turns.append(turn)
        self.save_session(session)
        return turn


session_manager = SessionManager()

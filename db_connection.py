"""
Database Connection Manager for PostgreSQL.
Provides a generic connection factory supporting:
- Environment variable configuration
- Runtime configuration parameter dictionary
- Secure password masking (never prints plain text passwords)
- Enforced Read-Only PostgreSQL session mode
"""

import os
from typing import Dict, Any, Optional
import psycopg2


def load_dotenv_file(filepath: Optional[str] = None) -> None:
    """Simple helper to load key-value pairs from a .env file into os.environ if present."""
    env_path = filepath or os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and not os.getenv(key):
                        os.environ[key] = val
        except Exception:
            pass


class DBConfig:
    """Encapsulates PostgreSQL connection parameters with safe masking."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        dbname: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        env_file: Optional[str] = None,
    ):
        load_dotenv_file(env_file)

        self.host = host or os.getenv("PGHOST") or os.getenv("DB_HOST", "localhost")
        self.port = int(port or os.getenv("PGPORT") or os.getenv("DB_PORT", "5432"))
        self.dbname = dbname or os.getenv("PGDATABASE") or os.getenv("DB_NAME", "postgres")
        self.user = user or os.getenv("PGUSER") or os.getenv("DB_USER", "postgres")
        self.password = password or os.getenv("PGPASSWORD") or os.getenv("DB_PASSWORD", "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
        }

    def safe_repr(self) -> str:
        """Returns connection info string with password securely masked."""
        return (
            f"PostgreSQL Config [host={self.host}:{self.port}, "
            f"dbname='{self.dbname}', user='{self.user}', password=*****]"
        )

    def __repr__(self) -> str:
        return self.safe_repr()


class DatabaseConnection:
    """Manages a single read-only PostgreSQL connection lifecycle."""

    def __init__(self, config: Optional[DBConfig] = None):
        self.config = config or DBConfig()
        self.conn = None

    def connect(self, readonly: bool = True):
        """Establishes connection to PostgreSQL and sets session read-only if requested."""
        cfg = self.config.to_dict()
        self.conn = psycopg2.connect(
            dbname=cfg["dbname"],
            user=cfg["user"],
            password=cfg["password"],
            host=cfg["host"],
            port=cfg["port"],
            connect_timeout=10,
        )
        if readonly:
            self.conn.set_session(readonly=True)
        return self.conn

    def close(self):
        """Closes connection safely if open."""
        if self.conn and not self.conn.closed:
            self.conn.close()

    def __enter__(self):
        self.connect(readonly=True)
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

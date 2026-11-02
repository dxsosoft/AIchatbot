"""
Automatic Schema & Metadata Discovery Engine for PostgreSQL.
Discovers database structure dynamically without hardcoded table/column names.
"""

from typing import Dict, Any, List, Optional
import psycopg2


class SchemaInspector:
    """Discovers tables, columns, data types, primary keys, foreign keys, and sample data."""

    def __init__(self, conn):
        self.conn = conn

    def get_database_name(self) -> str:
        """Retrieves the current connected database name."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT current_database();")
            return cur.fetchone()[0]

    def get_schemas(self) -> List[str]:
        """Lists accessible user schemas excluding system schemas."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                  AND schema_name NOT LIKE 'pg_temp_%%'
                  AND schema_name NOT LIKE 'pg_toast_temp_%%'
                ORDER BY schema_name;
            """)
            return [r[0] for r in cur.fetchall()]

    def discover_tables(self, schema: str = "public") -> List[str]:
        """Discovers base tables in the target schema."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """, (schema,))
            return [r[0] for r in cur.fetchall()]

    def discover_columns(self, table: str, schema: str = "public") -> List[Dict[str, Any]]:
        """Discovers column name, data type, max length, and nullability."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position;
            """, (schema, table))
            columns = []
            for c_name, d_type, char_len, nullable in cur.fetchall():
                dtype_str = d_type if not char_len else f"{d_type}({char_len})"
                columns.append({
                    "column_name": c_name,
                    "data_type": dtype_str,
                    "is_nullable": nullable
                })
            return columns

    def discover_primary_keys(self, table: str, schema: str = "public") -> List[str]:
        """Discovers primary key column names for a table."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = %s
                  AND tc.table_name = %s;
            """, (schema, table))
            return [r[0] for r in cur.fetchall()]

    def discover_foreign_keys(self, table: str, schema: str = "public") -> List[Dict[str, str]]:
        """Discovers foreign key relationships for a table."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM 
                    information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND tc.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' 
                  AND tc.table_schema = %s
                  AND tc.table_name = %s;
            """, (schema, table))
            return [
                {
                    "column": r[0],
                    "foreign_table": r[1],
                    "foreign_column": r[2]
                }
                for r in cur.fetchall()
            ]

    def get_row_count(self, table: str, schema: str = "public") -> int:
        """Gets exact total row count for a table."""
        with self.conn.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}";')
            return cur.fetchone()[0]

    def get_sample_data(self, table: str, schema: str = "public", limit: int = 10) -> List[Dict[str, Any]]:
        """Fetches up to `limit` sample rows from table."""
        with self.conn.cursor() as cur:
            cur.execute(f'SELECT * FROM "{schema}"."{table}" LIMIT %s;', (limit,))
            col_names = [desc[0] for desc in cur.description]
            sample_rows = []
            for r in cur.fetchall():
                row_dict = {}
                for col, val in zip(col_names, r):
                    row_dict[col] = str(val) if val is not None else None
                sample_rows.append(row_dict)
            return sample_rows

    def discover_full_schema(self, schema: str = "public", include_sample_data: bool = True) -> Dict[str, Any]:
        """Discovers full metadata structure for the entire database."""
        db_name = self.get_database_name()
        schemas = self.get_schemas()
        tables = self.discover_tables(schema=schema)

        tables_metadata = {}
        total_rows = 0

        for table in tables:
            cols = self.discover_columns(table, schema=schema)
            pks = self.discover_primary_keys(table, schema=schema)
            fks = self.discover_foreign_keys(table, schema=schema)
            rc = self.get_row_count(table, schema=schema)
            total_rows += rc

            table_data = {
                "table_name": table,
                "row_count": rc,
                "columns": cols,
                "primary_keys": pks,
                "foreign_keys": fks
            }

            if include_sample_data:
                table_data["sample_data"] = self.get_sample_data(table, schema=schema, limit=10)

            tables_metadata[table] = table_data

        return {
            "database_name": db_name,
            "target_schema": schema,
            "available_schemas": schemas,
            "tables_count": len(tables),
            "total_rows_count": total_rows,
            "tables": tables_metadata
        }

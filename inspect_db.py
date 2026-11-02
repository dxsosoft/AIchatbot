"""
Database Inspection Script for PostgreSQL (ordermgmt_db)
Strictly READ-ONLY inspection tool.
Reads connection parameters from .env file or system environment variables.
"""

import os
import sys
import json
import psycopg2

def load_dotenv_file():
    """Simple helper to load .env file if present in the current working directory."""
    env_path = os.path.join(os.getcwd(), ".env")
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

def get_env_config():
    """Retrieve database parameters safely from environment with defaults."""
    load_dotenv_file()
    
    host = os.getenv("PGHOST") or os.getenv("DB_HOST", "localhost")
    port = os.getenv("PGPORT") or os.getenv("DB_PORT", "5432")
    dbname = os.getenv("PGDATABASE") or os.getenv("DB_NAME", "ordermgmt_db")
    user = os.getenv("PGUSER") or os.getenv("DB_USER", "postgres")
    password = os.getenv("PGPASSWORD") or os.getenv("DB_PASSWORD", "")

    return {
        "host": host,
        "port": int(port),
        "dbname": dbname,
        "user": user,
        "password": password
    }

def list_available_databases(config):
    """Safely connect to 'postgres' system database to check available database names."""
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user=config['user'],
            password=config['password'],
            host=config['host'],
            port=config['port'],
            connect_timeout=3
        )
        cur = conn.cursor()
        cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;")
        dbs = [r[0] for r in cur.fetchall()]
        conn.close()
        return dbs
    except Exception:
        return None

def inspect_database():
    config = get_env_config()
    
    print("==================================================")
    print("       ORDERMGMT_DB READ-ONLY INSPECTION          ")
    print("==================================================")
    print(f"Connecting to database '{config['dbname']}' on {config['host']}:{config['port']} as user '{config['user']}'...")

    try:
        conn = psycopg2.connect(
            dbname=config['dbname'],
            user=config['user'],
            password=config['password'],
            host=config['host'],
            port=config['port'],
            connect_timeout=5
        )
    except Exception as e:
        err_msg = str(e).strip()
        print(f"\n[ERROR] Connection failed: {err_msg}\n")

        # If authentication failed
        if "password authentication failed" in err_msg:
            print("--> Password authentication failed for user '%s'." % config['user'])
            print("Please check your password in .env (PGPASSWORD=...) or environment variables.")
        # If database does not exist
        elif "does not exist" in err_msg:
            print("--> Database '%s' was not found on this PostgreSQL server." % config['dbname'])
            available = list_available_databases(config)
            if available:
                print("Available databases on this server: %s" % available)
            else:
                print("Could not list databases on server.")

        print("\nRequired / Optional Configuration:")
        print("  - PGHOST / DB_HOST      (Current: %s)" % config['host'])
        print("  - PGPORT / DB_PORT      (Current: %s)" % config['port'])
        print("  - PGDATABASE / DB_NAME  (Current: %s)" % config['dbname'])
        print("  - PGUSER / DB_USER      (Current: %s)" % config['user'])
        print("  - PGPASSWORD / DB_PASSWORD (Set: %s)" % ("Yes" if config['password'] else "No"))
        sys.exit(1)

    # Enforce Read-Only session mode for strict safety
    conn.set_session(readonly=True)
    cur = conn.cursor()

    # 1. PostgreSQL Version
    cur.execute("SELECT version();")
    pg_version = cur.fetchone()[0]
    print(f"\n[PostgreSQL Version]\n{pg_version}\n")

    # 2. Retrieve all base tables in the public schema
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cur.fetchall()]

    if not tables:
        print("No user tables found in 'public' schema.")
        cur.close()
        conn.close()
        return

    print(f"[Tables Found]: {len(tables)}")
    for t in tables:
        print(f"  - {t}")
    print("\n" + "="*50)

    report_data = {
        "postgres_version": pg_version,
        "database_name": config['dbname'],
        "tables_count": len(tables),
        "tables": {}
    }

    for table in tables:
        print(f"\n>>> Table: {table}")
        table_info = {"table_name": table}

        # Row Count
        cur.execute(f'SELECT COUNT(*) FROM "{table}";')
        row_count = cur.fetchone()[0]
        table_info["row_count"] = row_count
        print(f"  Total Rows: {row_count}")

        # Columns & Data Types
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
        """, (table,))
        columns = []
        print("  Columns:")
        for c_name, d_type, char_len, nullable in cur.fetchall():
            dtype_str = d_type if not char_len else f"{d_type}({char_len})"
            columns.append({
                "column_name": c_name,
                "data_type": dtype_str,
                "is_nullable": nullable
            })
            print(f"    - {c_name} ({dtype_str}, nullable={nullable})")
        table_info["columns"] = columns

        # Primary Keys
        cur.execute("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = 'public'
              AND tc.table_name = %s;
        """, (table,))
        primary_keys = [r[0] for r in cur.fetchall()]
        table_info["primary_keys"] = primary_keys
        print(f"  Primary Key(s): {', '.join(primary_keys) if primary_keys else 'None'}")

        # Foreign Keys / Relationships
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
              AND tc.table_schema = 'public'
              AND tc.table_name = %s;
        """, (table,))
        foreign_keys = []
        fk_rows = cur.fetchall()
        if fk_rows:
            print("  Foreign Key(s):")
            for column_name, foreign_table_name, foreign_column_name in fk_rows:
                foreign_keys.append({
                    "column": column_name,
                    "foreign_table": foreign_table_name,
                    "foreign_column": foreign_column_name
                })
                print(f"    - {column_name} -> {foreign_table_name}({foreign_column_name})")
        else:
            print("  Foreign Key(s): None")
        table_info["foreign_keys"] = foreign_keys

        # Sample Data (First 10 Rows)
        cur.execute(f'SELECT * FROM "{table}" LIMIT 10;')
        col_names = [desc[0] for desc in cur.description]
        sample_rows = []
        for r in cur.fetchall():
            row_dict = {}
            for col, val in zip(col_names, r):
                row_dict[col] = str(val) if val is not None else None
            sample_rows.append(row_dict)
        table_info["sample_data"] = sample_rows
        print(f"  Sample Data ({len(sample_rows)} rows loaded)")

        report_data["tables"][table] = table_info

    cur.close()
    conn.close()

    # Save detailed JSON report
    output_filename = "db_inspection_report.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print("\n==================================================")
    print(f"Inspection complete. Detailed report saved to {output_filename}")
    print("==================================================")

if __name__ == "__main__":
    inspect_database()

#!/usr/bin/env python3
"""Initialize SQLite database for database.

This script is intentionally written to be:
- Idempotent: safe to run multiple times without breaking existing data.
- Compatible with existing DB tooling expectations in this container:
  - Database file name is `myapp.db`
  - Connection info is written to `db_connection.txt`
  - Node viewer env is written to `db_visualizer/sqlite.env`

Schema created:
- app_info: metadata key/value pairs
- users: sample/example table preserved for backwards-compatibility with tooling
- notes: main table for the notes app (id, title, content, created_at, updated_at)
"""

import os
import sqlite3
from dataclasses import dataclass


DB_NAME = "myapp.db"
DB_USER = "kaviasqlite"  # Not used for SQLite, but kept for consistency
DB_PASSWORD = "kaviadefaultpassword"  # Not used for SQLite, but kept for consistency
DB_PORT = "5000"  # Not used for SQLite, but kept for consistency


@dataclass(frozen=True)
class InitDbResult:
    """Result of the initialization flow."""
    db_name: str
    db_path: str
    connection_string: str
    table_count: int
    app_info_record_count: int


# PUBLIC_INTERFACE
def init_db(db_name: str = DB_NAME) -> InitDbResult:
    """Initialize the SQLite DB schema and write tool-support files.

    Contract:
      Inputs:
        - db_name: SQLite file name (default: "myapp.db"). Relative path supported.

      Outputs:
        - InitDbResult describing DB location, connection string, and basic stats.

      Errors:
        - Raises sqlite3.Error if the database cannot be created/opened or schema DDL fails.
        - Raises OSError/IOError if the connection info files cannot be written.

      Side effects:
        - Creates/updates SQLite file on disk.
        - Creates/updates db_connection.txt
        - Creates/updates db_visualizer/sqlite.env
    """
    print("Starting SQLite setup...")

    db_exists = os.path.exists(db_name)
    if db_exists:
        print(f"SQLite database already exists at {db_name}")
        # Verify it's accessible
        try:
            conn = sqlite3.connect(db_name)
            conn.execute("SELECT 1")
            conn.close()
            print("Database is accessible and working.")
        except Exception as e:
            print(f"Warning: Database exists but may be corrupted: {e}")
    else:
        print("Creating new SQLite database...")

    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Ensure FK support is consistently enabled in environments that respect it.
    cursor.execute("PRAGMA foreign_keys = ON")

    # --- Schema (idempotent) ---

    # Existing tooling/sample table: keep as-is.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS app_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Existing tooling/sample table: keep as-is.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Notes table for the application.
    #
    # Design notes:
    # - Store timestamps as TIMESTAMP with CURRENT_TIMESTAMP default to keep SQLite simple.
    # - `updated_at` is set on insert and can be maintained by the application on updates
    #   (SQLite triggers could do it too, but we avoid introducing implicit behavior unless requested).
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Optional indexes for common usage patterns (safe / idempotent).
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_updated_at ON notes(updated_at)")

    # --- Seed metadata (idempotent) ---
    cursor.execute(
        "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
        ("project_name", "database"),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
        ("version", "0.1.0"),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
        ("author", "John Doe"),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
        ("description", ""),
    )

    conn.commit()

    # --- Stats ---
    cursor.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    table_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM app_info")
    record_count = cursor.fetchone()[0]

    conn.close()

    # --- Tooling files (preserve format/expectations) ---
    current_dir = os.getcwd()
    connection_string = f"sqlite:///{current_dir}/{db_name}"

    try:
        with open("db_connection.txt", "w") as f:
            f.write("# SQLite connection methods:\n")
            f.write(f"# Python: sqlite3.connect('{db_name}')\n")
            f.write(f"# Connection string: {connection_string}\n")
            f.write(f"# File path: {current_dir}/{db_name}\n")
        print("Connection information saved to db_connection.txt")
    except Exception as e:
        print(f"Warning: Could not save connection info: {e}")

    db_path = os.path.abspath(db_name)

    if not os.path.exists("db_visualizer"):
        os.makedirs("db_visualizer", exist_ok=True)
        print("Created db_visualizer directory")

    try:
        with open("db_visualizer/sqlite.env", "w") as f:
            f.write(f'export SQLITE_DB="{db_path}"\n')
        print("Environment variables saved to db_visualizer/sqlite.env")
    except Exception as e:
        print(f"Warning: Could not save environment variables: {e}")

    print("\nSQLite setup complete!")
    print(f"Database: {db_name}")
    print(f"Location: {current_dir}/{db_name}")
    print("")
    print("To use with Node.js viewer, run: source db_visualizer/sqlite.env")
    print("\nTo connect to the database, use one of the following methods:")
    print(f"1. Python: sqlite3.connect('{db_name}')")
    print(f"2. Connection string: {connection_string}")
    print(f"3. Direct file access: {current_dir}/{db_name}")
    print("")
    print("Database statistics:")
    print(f"  Tables: {table_count}")
    print(f"  App info records: {record_count}")

    # If sqlite3 CLI is available, show how to use it
    try:
        import subprocess

        result = subprocess.run(["which", "sqlite3"], capture_output=True, text=True)
        if result.returncode == 0:
            print("")
            print("SQLite CLI is available. You can also use:")
            print(f"  sqlite3 {db_name}")
    except Exception:
        pass

    print("\nScript completed successfully.")

    return InitDbResult(
        db_name=db_name,
        db_path=db_path,
        connection_string=connection_string,
        table_count=table_count,
        app_info_record_count=record_count,
    )


if __name__ == "__main__":
    init_db()

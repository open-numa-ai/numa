"""Persist and restore values with SQLiteMemory."""

from pathlib import Path

from numa.memory import SQLiteMemory


def main() -> None:
    """Write and read a JSON-compatible value from a local database."""
    database = Path("numa-memory.db")

    with SQLiteMemory(database) as memory:
        memory.set("project", {"name": "Numa", "phase": "v0.2"})
        print(memory.get("project"))


if __name__ == "__main__":
    main()

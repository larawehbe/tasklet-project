"""Initialize the Tasklet database from schema.sql + seed.sql.

Equivalent to running `support-agent init-db` once the CLI is wired up
(Phase 4). Run directly with: `python scripts/init_db.py`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import DB_PATH, init_db

if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")

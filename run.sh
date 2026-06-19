#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Install dependencies if needed
if ! python3 -c "import flask" 2>/dev/null; then
  echo "Installing dependencies..."
  pip3 install -r requirements.txt
fi

# Seed initial data if DB is empty
python3 -c "
import database as db
import os
db.init_db()
with db.get_conn() as conn:
    count = conn.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
if count == 0:
    import seed_data
    seed_data.seed()
    print('Initial data seeded.')
else:
    print(f'DB already has {count} articles.')
"

echo ""
echo "Starting Internal Link Manager..."
echo "Open http://localhost:5000 in your browser"
echo ""

python3 app.py

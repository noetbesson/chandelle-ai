"""Initialize the local schema and activity catalog, without creating user profiles."""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default='.runtime/chandelle_v2.sqlite3')
    args = parser.parse_args()
    # Select the database before importing the module-level ASGI app. An explicit
    # fixture path must never initialize the user's ordinary database as a side effect.
    os.environ['CHANDELLE_DB_PATH'] = str(Path(args.database).resolve())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.api.app import app
    from backend.streams.C_discovery.local_catalog import ImportedCatalog
    ImportedCatalog(app.state.v2['db']).import_bundle()
    print('Initialized schema and activity catalog; no user profiles:', args.database)


if __name__ == '__main__':
    main()

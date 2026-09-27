"""Normalize the supplied workbooks, export a small release, optionally import it.

Read-only inputs. Requires openpyxl only for --source; application runtime needs no Excel library.
"""
from pathlib import Path
import argparse
import gzip
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Folder containing the original xlsx files (Bar.xlsx is optional)')
    parser.add_argument('--bundle', type=Path, default=ROOT/'backend/streams/C_discovery/data/imported_catalog.jsonl.gz')
    parser.add_argument('--db', type=Path, help='Existing Chandelle SQLite path; omitted = prepare files only')
    args = parser.parse_args()
    if args.source:
        from backend.streams.C_discovery.import_normalize import normalize_directory
        records, report = normalize_directory(args.source)
        raw = ''.join(json.dumps(row, ensure_ascii=False, separators=(',', ':'), sort_keys=True)+'\n' for row in records).encode('utf-8')
        compressed = gzip.compress(raw, compresslevel=9, mtime=0)
        report.update(normalized_bytes=len(raw), bundle_bytes=len(compressed), format_version=1,
                      notes=['Original exports preserved.', 'Dollar symbols are price tiers, never EUR amounts.',
                             'Pint starting prices are not per-person outing budgets; offers remain unverified.', 'Import date is not a verification date.', 'Films are references, not screenings.',
                             'Only a shortlist is sent to web search when needed.'])
        args.bundle.parent.mkdir(parents=True, exist_ok=True)
        temp = args.bundle.with_suffix('.tmp')
        temp.write_bytes(compressed)
        temp.replace(args.bundle)
        args.bundle.with_name('import_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=True))
    if args.db:
        from backend.db import Database
        from backend.streams.C_discovery.local_catalog import ImportedCatalog
        catalog = ImportedCatalog(Database(args.db))
        print(json.dumps(catalog.import_bundle(args.bundle), ensure_ascii=True))
        print(json.dumps(catalog.status()))
    if not args.source and not args.db:
        parser.error('Specify --source and/or --db')


if __name__ == '__main__':
    main()

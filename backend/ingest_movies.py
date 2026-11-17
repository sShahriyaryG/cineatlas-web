"""Download a reproducible CSV snapshot and import it using existing DB config."""
import argparse
import csv
import io
import json
import sys
from dataclasses import asdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionLocal
from app.ingestion import ingest

ENDPOINT = 'https://query.wikidata.org/sparql'
QUERY = Path(__file__).resolve().parent / 'data' / 'wikidata_films.sparql'
MAX_BYTES = 5 * 1024 * 1024


def fetch(destination: Path, contact: str) -> None:
    """Fetch once; no automatic retry storm and no partial snapshot on failure."""
    if not contact.strip() or '\n' in contact or '\r' in contact:
        raise ValueError('Provide a contact URL or email for the User-Agent')
    if destination.exists():
        raise ValueError(f'{destination} already exists; use a new filename')
    url = ENDPOINT + '?' + urlencode({
    'query': QUERY.read_text(encoding='utf-8')
})
    request = Request(url, headers={'Accept': 'text/csv', 'User-Agent': f'CineAtlas/0.4 (movie catalog ingestion; {contact})'})
    with urlopen(request, timeout=90) as response:
        if response.headers.get_content_type() != 'text/csv':
            preview = response.read(300).decode('utf-8', errors='replace')
            raise ValueError(
                f"Wikidata did not return CSV. "
                f"Content-Type: {response.headers.get('Content-Type')}. "
                f"Response preview: {preview!r}"
            )
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES or not data:
        raise ValueError('Empty or oversized snapshot')
    from app.ingestion import COLUMNS
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')), strict=True)
    if not reader.fieldnames or not COLUMNS.issubset(reader.fieldnames) or next(reader, None) is None:
        raise ValueError('No film rows or invalid snapshot header')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as output:
        output.write(data)
    print(f'Saved {len(data)} bytes to {destination}')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    get = sub.add_parser('fetch', help='Save the curated Wikidata query as CSV')
    get.add_argument('--output', type=Path, required=True)
    get.add_argument('--contact', required=True, help='Contact URL or email for Wikidata requests')
    load = sub.add_parser('import', help='Import a saved CSV snapshot')
    load.add_argument('csv', type=Path)
    load.add_argument('--dry-run', action='store_true', help='Preview counts without writes')
    load.add_argument('--strict', action='store_true', help='Abort if any row is invalid')
    args = parser.parse_args(argv)
    try:
        if args.command == 'fetch':
            fetch(args.output, args.contact)
        else:
            with args.csv.open(encoding='utf-8-sig', newline='') as stream, SessionLocal() as db:
                report = ingest(db, stream, dry_run=args.dry_run, strict=args.strict)
                if args.dry_run:
                    db.rollback()
                else:
                    db.commit()
            print(json.dumps(asdict(report), indent=2))
        return 0
    except HTTPError as exc:
        print(f'Wikidata HTTP {exc.code}; retry later or use a CSV exported from the query service.', file=sys.stderr)
    except (ValueError, OSError, URLError, SQLAlchemyError) as exc:
        print(f'Operation failed: {exc}', file=sys.stderr)
    except csv.Error as exc:
        print(f'Invalid CSV: {exc}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())

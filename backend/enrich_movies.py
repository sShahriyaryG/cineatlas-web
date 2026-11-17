"""Preview or apply TMDB enrichment using a verified Wikidata snapshot."""
import argparse
import csv
import getpass
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from app.db import SessionLocal
from app.enrichment import TMDBClient, ProviderError, read_mapping, enrich


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--apply', action='store_true', help='Commit changes; default is rollback preview')
    modes.add_argument('--dry-run', action='store_true', help='Preview changes in a rolled-back transaction')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--cast-limit', type=int, default=12)
    args = parser.parse_args(argv)
    if (args.limit is not None and args.limit < 1) or not 1 <= args.cast_limit <= 50:
        parser.error('limit must be positive and cast-limit must be 1–50')
    try:
        with args.csv.open(encoding='utf-8-sig', newline='') as stream:
            mapping = read_mapping(stream)
        token = os.environ.get('TMDB_READ_TOKEN', '').strip()
        if not token:
            if not sys.stdin.isatty():
                raise ValueError('Run in an interactive terminal or supply TMDB_READ_TOKEN securely')
            token = getpass.getpass('TMDB API Read Access Token (hidden): ')
        with TMDBClient(token) as provider, SessionLocal() as db:
            try:
                report = enrich(db, mapping, provider, limit=args.limit, cast_limit=args.cast_limit, dry_run=not args.apply)
                if args.apply:
                    db.commit()
                else:
                    db.rollback()
            except BaseException:
                db.rollback()
                raise
        print(json.dumps(asdict(report), indent=2))
        return 0
    except (ValueError, OSError, csv.Error, ProviderError) as exc:
        print(f'Enrichment failed: {exc}', file=sys.stderr)
    except SQLAlchemyError:
        print('Enrichment failed: database transaction rolled back; check migration and constraints', file=sys.stderr)
    except (KeyboardInterrupt, EOFError):
        print('Enrichment cancelled', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())

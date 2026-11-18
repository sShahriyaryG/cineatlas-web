"""Preview or apply extended TMDB enrichment of already-linked catalog records."""
import argparse
from dataclasses import asdict
import getpass
import json
import os
import sys

from sqlalchemy.exc import SQLAlchemyError
from app.db import SessionLocal
from app.enrichment import ProviderError
from app.enrichment_v2 import EnrichmentClient, enrich_linked


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--apply', action='store_true', help='Commit the selected batch')
    modes.add_argument('--dry-run', action='store_true', help='Preview (default); roll back all writes')
    parser.add_argument('--limit', type=int, help='Maximum linked movies, ordered by local ID')
    parser.add_argument('--after-movie-id', type=int, default=0, help='Only local movie IDs greater than this value')
    parser.add_argument('--cast-limit', type=int, default=12)
    args=parser.parse_args(argv)
    if (args.limit is not None and args.limit<1) or args.after_movie_id<0 or not 1<=args.cast_limit<=50:
        parser.error('limit must be positive, after-movie-id nonnegative and cast-limit 1–50')
    try:
        token=os.environ.get('TMDB_READ_TOKEN','').strip()
        if not token:
            if not sys.stdin.isatty():
                raise ValueError('Run in an interactive terminal or supply TMDB_READ_TOKEN securely')
            token=getpass.getpass('TMDB API Read Access Token (hidden): ')
        with EnrichmentClient(token) as provider, SessionLocal() as db:
            try:
                report=enrich_linked(db,provider,limit=args.limit,after_movie_id=args.after_movie_id,
                    cast_limit=args.cast_limit,dry_run=not args.apply,progress=lambda s:print(s,file=sys.stderr,flush=True))
                if args.apply:
                    db.commit()
                else:
                    db.rollback()
            except BaseException:
                db.rollback()
                raise
        print(json.dumps(asdict(report),indent=2))
        return 0
    except (ValueError, ProviderError) as exc:
        print(f'Enrichment failed: {exc}',file=sys.stderr)
    except SQLAlchemyError:
        print('Enrichment failed: database transaction rolled back; check migration and constraints',file=sys.stderr)
    except (KeyboardInterrupt,EOFError):
        print('Enrichment cancelled',file=sys.stderr)
    return 1


if __name__=='__main__':
    raise SystemExit(main())

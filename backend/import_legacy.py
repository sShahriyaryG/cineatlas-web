"""Import movie metadata from the original university ZIP archive.

Usage: python import_legacy.py /path/to/40131849.zip
Never imports legacy users or SHA-256 password hashes.
"""
import csv,io,json,sys,zipfile
from datetime import date
from sqlalchemy import select
from app.db import Base,engine,SessionLocal
from app.models import Movie
from app.catalog import set_movie_genres

def import_movies(archive):
    Base.metadata.create_all(bind=engine)
    with zipfile.ZipFile(archive) as z:
        name=next((x for x in z.namelist() if x.endswith('db_data/movies.csv')),None)
        if not name:raise ValueError('movies.csv not found in archive')
        with z.open(name) as f:
            rows=list(csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig',newline='')))
    created=skipped=0
    with SessionLocal() as db:
        for row in rows:
            try:
                legacy_id=row['uuid']
                if db.scalar(select(Movie.id).where(Movie.legacy_id==legacy_id)):
                    skipped+=1;continue
                try:genres=json.loads(row.get('genres') or '[]')
                except json.JSONDecodeError:genres=[]
                yr=int(row['release_date'][:4])
                if not (1888<=yr<=2200):raise ValueError('Invalid year')
                title=(row.get('title') or '').strip()
                if not title:raise ValueError('Missing title')
                movie = Movie(title=title[:240],year=yr,synopsis=(row.get('plot_summary') or '')[:10000],language=(row.get('language') or '')[:100],country=(row.get('country') or '')[:100],legacy_id=legacy_id)
                if not isinstance(genres, list):
                    raise ValueError('Expected a list of genres')
                genre_text = ','.join(str(x).strip().replace(',', ' / ') for x in genres)
                if len(genre_text) > 4096:
                    raise ValueError('Genre list exceeds 4096 characters')
                set_movie_genres(db, movie, genre_text)
                db.add(movie)
                created+=1
            except (KeyError,ValueError,TypeError) as exc:
                skipped+=1;print('Skipped record:',str(exc))
        db.commit()
    print(f'Imported {created} movies, skipped {skipped} rows. Review imported user-authored content before publication.')
if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python import_legacy.py /path/to/archive.zip')
    import_movies(sys.argv[1])

"""Read-only archive directories. Counts refer to distinct local films."""
from typing import Literal
from sqlalchemy import select, func, or_, case
from .models import (Movie, Person, PersonMetadata, PersonAlternativeName, MovieCredit,
                     Genre, MovieGenre, Language, MovieLanguage, Country, MovieCountry, Tag, MovieTag)

Category = Literal['genres', 'languages', 'countries', 'tags']
CLASSIFICATIONS = {
    'genres': (Genre, MovieGenre, MovieGenre.genre_id),
    'languages': (Language, MovieLanguage, MovieLanguage.language_id),
    'countries': (Country, MovieCountry, MovieCountry.country_id),
    'tags': (Tag, MovieTag, MovieTag.tag_id),
}


def directory_order(name, count, q, sort):
    if sort == 'name_desc': return [func.lower(name).desc()]
    if sort == 'count_desc': return [count.desc(), func.lower(name)]
    if sort == 'count_asc': return [count, func.lower(name)]
    if sort == 'relevance' and q:
        return [case((func.lower(name)==q.lower(),0),(name.istartswith(q,autoescape=True),1),else_=2),func.lower(name)]
    return [func.lower(name)]


def people_page(db, q, role, page, size, sort='name'):
    q=' '.join(q.split())
    stmt = select(Person.id, Person.name, PersonMetadata.profile_url).outerjoin(
        PersonMetadata, PersonMetadata.person_id == Person.id)
    for term in q.split():
        stmt = stmt.where(or_(Person.name.icontains(term, autoescape=True),
            PersonMetadata.full_name.icontains(term, autoescape=True),
            select(PersonAlternativeName.person_id).where(
                PersonAlternativeName.person_id == Person.id,
                PersonAlternativeName.name.icontains(term, autoescape=True)).exists()))
    if role:
        stmt = stmt.where(select(MovieCredit.id).where(MovieCredit.person_id == Person.id,
                                                       MovieCredit.role == role).exists())
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    film_count = select(func.count(func.distinct(MovieCredit.movie_id))).where(MovieCredit.person_id == Person.id).correlate(Person).scalar_subquery()
    rows = db.execute(stmt.order_by(*directory_order(Person.name,film_count,q,sort), Person.id).offset((page-1)*size).limit(size)).all()
    ids = [r.id for r in rows]
    roles = {pid: [] for pid in ids}
    counts = {}
    if ids:
        for pid, r in db.execute(select(MovieCredit.person_id, MovieCredit.role).where(
                MovieCredit.person_id.in_(ids)).distinct().order_by(MovieCredit.role)):
            roles[pid].append(r)
        counts = dict(db.execute(select(MovieCredit.person_id, func.count(func.distinct(MovieCredit.movie_id)))
            .where(MovieCredit.person_id.in_(ids)).group_by(MovieCredit.person_id)).all())
    return {'items': [dict(id=r.id, name=r.name, profile_url=r.profile_url,
                           roles=roles[r.id], film_count=counts.get(r.id, 0)) for r in rows],
            'total': total, 'page': page, 'size': size}


def classification_page(db, category, q, page, size, sort='name'):
    q=' '.join(q.split())
    model, link, fk = CLASSIFICATIONS[category]
    counts = select(fk.label('cid'), func.count(func.distinct(link.movie_id)).label('n')).group_by(fk).subquery()
    # Only classifications attached to films appear in browse results. Direct links
    # to existing but now-unused classifications still resolve to an empty page.
    stmt = select(model.id, model.name, counts.c.n).join(counts, counts.c.cid == model.id)
    if q:
        stmt = stmt.where(model.name.icontains(q, autoescape=True))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(*directory_order(model.name,counts.c.n,q,sort), model.id).offset((page-1)*size).limit(size))
    return {'items': [dict(id=i, name=n, film_count=c) for i, n, c in rows],
            'total': total, 'page': page, 'size': size}


def filter_options(db):
    """All used classifications, with stable IDs; no certification-only countries."""
    result = {}
    for category, (model, link, fk) in CLASSIFICATIONS.items():
        stmt = select(model.id, model.name).where(
            select(link.movie_id).where(fk == model.id).correlate(model).exists()
        ).order_by(func.lower(model.name), model.id)
        result[category] = [dict(id=i, name=n) for i, n in db.execute(stmt)]
    return result


def movie_classifications(db, mid):
    result = {}
    for category, (model, link, fk) in CLASSIFICATIONS.items():
        stmt = select(model.id, model.name).join(link, fk == model.id).where(link.movie_id == mid)
        if category == 'languages':
            stmt = stmt.add_columns(link.kind).order_by(link.kind, func.lower(model.name), model.id)
            result[category] = [dict(id=i, name=n, kind=k) for i, n, k in db.execute(stmt)]
        else:
            result[category] = [dict(id=i, name=n) for i, n in db.execute(stmt.order_by(func.lower(model.name), model.id))]
    return result

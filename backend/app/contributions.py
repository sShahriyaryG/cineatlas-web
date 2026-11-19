"""Drafts, review and catalog publication. No catalog writes until approval."""
import json
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import Field, AfterValidator, ValidationError, model_validator
from sqlalchemy import select, func, exists, literal, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import get_db
from .catalog import parse_genres, set_movie_genres
from .catalog_lock import lock_catalog
from .metadata import (StrictInput, TitleLabel, ExternalURL, CreditRole, clean, safe_url,
    MovieMetadataPatch, PersonMetadataPatch, movie_metadata_out, person_metadata_out,
    apply_movie_metadata, apply_person_metadata, record_overrides)
from .models import (Contribution, User, Movie, Person, MovieCredit, EditSuggestion,
    MovieMetadataOverride, PersonMetadataOverride, MovieMetadata, PersonMetadata,
    MovieLanguage, MovieCountry, utcnow)
from .security import require_role

def friendly_validation(exc):
    """Describe invalid fields without exposing Pydantic diagnostics or input values."""
    labels = {'year': 'Release year', 'runtime': 'Runtime', 'source_url': 'Supporting source URL',
              'profile_url': 'Profile photograph URL', 'deathday': 'Date of death',
              'related_id': 'Related record', 'poster_url': 'Poster URL', 'trailer_url': 'Trailer URL'}
    messages = []
    for e in exc.errors():
        loc = [x for x in e['loc'] if x not in ('body', 'query', 'path', 'changes', 'core', 'metadata')]
        field = ' '.join(f'#{x+1}' if isinstance(x,int) else labels.get(x, x.replace('_',' ').capitalize()) for x in loc) or 'Contribution'
        kind = e['type']; ctx = e.get('ctx') or {}
        key = loc[-1] if loc else None
        if key == 'year' and kind in ('greater_than_equal','less_than_equal','int_parsing','int_type','int_from_float'):
            msg = 'Enter a whole release year between 1888 and 2200.'
        elif key == 'runtime' and kind in ('greater_than_equal','less_than_equal','int_parsing','int_type','int_from_float'):
            msg = 'Enter a whole runtime between 1 and 10,000 minutes.'
        elif kind == 'missing': msg = f'{field}: This field is required.'
        elif kind == 'string_too_short': msg = f'{field}: Enter at least {ctx.get("min_length",1)} character(s).'
        elif kind == 'string_too_long': msg = f'{field}: Use at most {ctx.get("max_length")} characters.'
        elif kind == 'too_long': msg = f'{field}: Use at most {ctx.get("max_length")} entries.'
        elif kind.startswith('date_'): msg = f'{field}: Enter a valid calendar date.'
        elif kind == 'value_error' and isinstance(key,str) and key.endswith('_url'): msg = f'{field}: Enter a valid HTTP or HTTPS URL without credentials.'
        elif kind == 'value_error' and 'Only actors may have a character name' in e['msg']: msg = f'{field}: Only actors may have a character name.'
        else: msg = f'{field}: Enter a valid value.'
        if msg not in messages: messages.append(msg)
    return '\n'.join(messages) or 'Check the contribution fields and try again.'


class ContributionRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def handle(request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                raise HTTPException(422, friendly_validation(exc)) from exc
        return handle


router = APIRouter(prefix='/api', route_class=ContributionRoute)
editor = require_role('editor','admin')
admin = require_role('admin')
Entity = Literal['movie','person']
Status = Literal['draft','pending','approved','rejected','withdrawn']
Text = Annotated[str, Field(max_length=10000), AfterValidator(clean)]
Short = Annotated[str, Field(max_length=240), AfterValidator(clean)]

class MovieCore(StrictInput):
    title: TitleLabel | None = None
    year: int | None = Field(default=None, ge=1888, le=2200)
    genres: list[TitleLabel] = Field(default_factory=list, max_length=50)
    synopsis: Text = ''
    poster_url: Annotated[str, Field(max_length=600), AfterValidator(lambda v: safe_url(v) if v else '')] = ''
    runtime: int | None = Field(default=None, ge=1, le=10000)

class PersonCore(StrictInput):
    name: TitleLabel | None = None
    biography: Text = ''

class Credit(StrictInput):
    related_id: int = Field(gt=0, le=2147483647)
    role: CreditRole
    character: Short = ''
    position: int | None = Field(default=None, ge=0, le=10000)
    @model_validator(mode='after')
    def actor_only(self):
        if self.role != 'actor' and self.character: raise ValueError('Only actors may have a character name')
        return self

class Changes(StrictInput):
    core: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
    credits: list[Credit] | None = Field(default=None, max_length=500)

class Draft(StrictInput):
    changes: Changes
    reason: Annotated[str, Field(max_length=1000), AfterValidator(clean)] = ''
    source_url: ExternalURL | None = None

class CreateDraft(Draft):
    entity: Entity
    target_id: int | None = Field(default=None, gt=0)
    baseline: dict | None = None

class UpdateDraft(Draft):
    version: int = Field(gt=0)

class Version(StrictInput):
    version: int = Field(gt=0)

class Decision(Version):
    decision: Literal['approved','rejected']
    note: Annotated[str, Field(max_length=1000), AfterValidator(clean)] = ''

def dump(value):
    return json.dumps(jsonable_encoder(value), ensure_ascii=False, sort_keys=True)

def snapshot(db, entity, identity):
    if identity is None: return {'core':{}, 'metadata':{}, 'credits':[]}
    record = db.get(Movie if entity=='movie' else Person, identity)
    if not record: raise HTTPException(404,'Catalog record no longer exists')
    if entity=='movie':
        core={k:getattr(record,k) for k in ('title','year','synopsis','poster_url','runtime')}
        core['genres']=[g.name for g in record.genre_entries]
        metadata=movie_metadata_out(db,record); metadata.pop('movie_id')
        owner,related=MovieCredit.movie_id,MovieCredit.person_id
    else:
        core={k:getattr(record,k) for k in ('name','biography')}
        metadata=person_metadata_out(db,record); metadata.pop('person_id')
        owner,related=MovieCredit.person_id,MovieCredit.movie_id
    credits=[dict(related_id=i,role=r,character=c,**({'position':pos} if entity=='movie' else {})) for i,r,c,pos in db.execute(select(related,MovieCredit.role,MovieCredit.character,MovieCredit.position).where(owner==identity))]
    credits=ordered_credits(entity,credits)
    return jsonable_encoder(dict(core=core,metadata=metadata,credits=credits))

def ordered_credits(entity,credits):
    if entity=='movie':
        return sorted(credits,key=lambda c:(c['role'],c['position'] is None,c['position'] or 0,c['related_id'],c['character']))
    return sorted(credits,key=lambda c:(c['related_id'],c['role'],c['character']))

def normalize(entity, changes):
    try:
        core=(MovieCore if entity=='movie' else PersonCore).model_validate(changes.core)
        meta=(MovieMetadataPatch if entity=='movie' else PersonMetadataPatch).model_validate(changes.metadata)
        result={'core':core.model_dump(mode='json',exclude_unset=True), 'metadata':meta.model_dump(mode='json',exclude_unset=True)}
        if entity=='movie' and 'genres' in result['core']:
            if any(',' in x for x in core.genres): raise ValueError('Enter each genre separately')
            parse_genres(','.join(core.genres))
        if changes.credits is not None:
            keys=[(c.related_id,c.role,c.character) for c in changes.credits]
            if len(keys)!=len(set(keys)):raise ValueError('Duplicate credit')
            if entity=='person' and any(c.position is not None for c in changes.credits):raise ValueError('Credit ordering belongs to the movie, not the person')
            result['credits']=ordered_credits(entity,[c.model_dump(exclude={'position'} if entity=='person' else set()) for c in changes.credits])
        return result
    except ValidationError as exc: raise HTTPException(422, friendly_validation(exc)) from exc
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc

def difference(baseline, proposed):
    return {**{g:{k:v for k,v in proposed[g].items() if k not in baseline[g] or baseline[g][k]!=v} for g in ('core','metadata')}, **({'credits':proposed['credits']} if 'credits' in proposed and proposed['credits']!=baseline['credits'] else {})}

def output(item):
    return dict(id=item.id, entity=item.entity,target_id=item.target_id,result_id=item.result_id,author_name=item.author_name,status=item.status,baseline=json.loads(item.baseline),changes=json.loads(item.changes),reason=item.reason,source_url=item.source_url,reviewer_name=item.reviewer_name,review_note=item.review_note,version=item.version,created_at=item.created_at,updated_at=item.updated_at)

def get_item(db, identity, user=None):
    item=db.scalar(select(Contribution).where(Contribution.id==identity).with_for_update())
    if not item or (user is not None and item.user_id!=user.id):raise HTTPException(404,'Contribution not found')
    return item

def check(item, version, status):
    if item.status!=status or item.version!=version:raise HTTPException(409,'Contribution changed; reload and try again')

def touch(item):
    item.version+=1; item.updated_at=utcnow()

def assert_current(db,item):
    try: current=snapshot(db,item.entity,item.target_id)
    except HTTPException as exc: raise HTTPException(409,'Catalog record was removed') from exc
    if current!=json.loads(item.baseline):raise HTTPException(409,'Catalog changed since this draft was started; create a revised proposal using current values')

def apply(db,item):
    """Caller holds catalog lock; commits or rolls back."""
    entity=item.entity; changes=json.loads(item.changes); baseline=json.loads(item.baseline)
    core,meta=changes['core'],changes['metadata']; identity=item.target_id
    new=identity is None
    if entity=='movie':
        if (new and (not core.get('title') or not core.get('year'))) or ('title' in core and not core['title']) or ('year' in core and core['year'] is None):
            raise HTTPException(422,'A title and release year are required')
        record=Movie(title=core['title'],year=core['year'],genres='') if new else db.get(Movie,identity)
        title=core.get('title',record.title); year=core.get('year',record.year)
        if new or title!=record.title or year!=record.year:
            duplicate=select(Movie.id).where(func.lower(Movie.title)==title.lower(),Movie.year==year)
            if not new:duplicate=duplicate.where(Movie.id!=identity)
            if db.scalar(duplicate.limit(1)):raise HTTPException(409,'A movie with this title and year already exists')
        db.add(record)
        for k,v in core.items():
            if k!='genres':setattr(record,k,v)
        db.flush()
        if 'genres' in core:set_movie_genres(db,record,','.join(core['genres']))
        apply_movie_metadata(db,record,MovieMetadataPatch.model_validate(meta))
        record_overrides(db,MovieMetadataOverride,'movie_id',record.id,set(core)|set(meta))
        owner='movie_id'; related='person_id'; refmodel=Person
    else:
        if (new and not core.get('name')) or ('name' in core and not core['name']):raise HTTPException(422,'A person name is required')
        record=Person(name=core['name']) if new else db.get(Person,identity)
        name=core.get('name',record.name); birthday=meta.get('birthday',baseline['metadata'].get('birthday'))
        if new or name!=record.name or 'birthday' in meta:
            candidates=db.execute(select(Person.id,PersonMetadata.birthday).outerjoin(PersonMetadata,PersonMetadata.person_id==Person.id).where(func.lower(Person.name)==name.lower())).all()
            if any(pid!=identity and (not birthday or not born or born.isoformat()==birthday) for pid,born in candidates):
                raise HTTPException(409,'Possible duplicate person; same name and no distinct verified birthday')
        db.add(record)
        for k,v in core.items():setattr(record,k,v)
        db.flush(); apply_person_metadata(db,record,PersonMetadataPatch.model_validate(meta))
        record_overrides(db,PersonMetadataOverride,'person_id',record.id,set(core)|set(meta))
        owner='person_id'; related='movie_id'; refmodel=Movie
    if 'credits' in changes:
        prior={(getattr(c,related),c.role,c.character):c for c in db.scalars(select(MovieCredit).where(getattr(MovieCredit,owner)==record.id))}
        proposed={(c['related_id'],c['role'],c['character']):c for c in changes['credits']}
        ids={i for i,_,_ in proposed}
        if ids and set(db.scalars(select(refmodel.id).where(refmodel.id.in_(ids))))!=ids:raise HTTPException(422,'A referenced film or person no longer exists')
        altered=prior.keys()^proposed.keys()
        for key in prior.keys()-proposed.keys():db.delete(prior[key])
        for i,role,character in proposed.keys()-prior.keys():db.add(MovieCredit(**{owner:record.id,related:i,'role':role,'character':character,'position':proposed[(i,role,character)].get('position')}))
        if entity=='movie':
            for key in prior.keys() & proposed.keys():
                pos=proposed[key].get('position')
                if prior[key].position!=pos:prior[key].position=pos;altered.add(key)
        for i,role,_ in altered:
            record_overrides(db,MovieMetadataOverride,'movie_id',record.id if entity=='movie' else i,{'credits_'+role})
    db.flush()
    return record.id

def validate(db,item):
    if len(item.reason.strip())<5:raise HTTPException(422,'Provide a contribution reason (at least 5 characters)')
    changes=json.loads(item.changes)
    if not (changes['core'] or changes['metadata'] or 'credits' in changes):raise HTTPException(422,'No changes to submit')
    try:
        with db.begin_nested() as nested:
            apply(db,item); nested.rollback()
    except ValidationError as exc:raise HTTPException(422,friendly_validation(exc)) from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    except IntegrityError as exc:raise HTTPException(409,'Catalog relationship conflicts') from exc

@router.get('/editor/catalog/{entity}/{identity}')
def current(entity:Entity,identity:int,user:User=Depends(editor),db:Session=Depends(get_db)):
    lock_catalog(db)
    return snapshot(db,entity,identity)

@router.get('/editor/missing/{entity}')
def incomplete(entity:Entity,field:str,page:int=Query(1,ge=1),size:int=Query(20,ge=1,le=50),user:User=Depends(editor),db:Session=Depends(get_db)):
    if entity=='movie':
        model=Movie; label=Movie.title
        conditions={'synopsis':Movie.synopsis=='','poster_url':Movie.poster_url=='','runtime':Movie.runtime.is_(None),
            'release_date':~exists(select(MovieMetadata.movie_id).where(MovieMetadata.movie_id==Movie.id,MovieMetadata.release_date.is_not(None))),
            'languages':~exists(select(MovieLanguage.movie_id).where(MovieLanguage.movie_id==Movie.id)),
            'countries':~exists(select(MovieCountry.movie_id).where(MovieCountry.movie_id==Movie.id))}
    else:
        model=Person;label=Person.name
        conditions={'biography':Person.biography==''}
        for key in ('profile_url','birthday','birthplace'):
            conditions[key]=~exists(select(PersonMetadata.person_id).where(PersonMetadata.person_id==Person.id,getattr(PersonMetadata,key).is_not(None)))
    if field not in conditions:raise HTTPException(422,'Unsupported missing field')
    stmt=select(model.id,label.label('label')).where(conditions[field]);total=db.scalar(select(func.count()).select_from(stmt.subquery()))
    return {'items':[dict(row._mapping) for row in db.execute(stmt.order_by(label,model.id).offset((page-1)*size).limit(size))],'total':total}

def history(db,status,page,size,owner=None,review=False):
    stmt=select(Contribution)
    if owner is not None:stmt=stmt.where(Contribution.user_id==owner)
    if review:stmt=stmt.where(Contribution.status!='draft')
    if status:stmt=stmt.where(Contribution.status==status)
    total=db.scalar(select(func.count()).select_from(stmt.subquery()))
    return {'items':[output(x) for x in db.scalars(stmt.order_by(Contribution.id.desc()).offset((page-1)*size).limit(size))],'total':total}

@router.get('/me/contributions')
def mine(status:Status|None=None,page:int=Query(1,ge=1),size:int=Query(20,ge=1,le=50),user:User=Depends(editor),db:Session=Depends(get_db)):
    return history(db,status,page,size,user.id)

@router.get('/admin/contributions')
def queue(status:Status|None=None,page:int=Query(1,ge=1),size:int=Query(20,ge=1,le=50),user:User=Depends(admin),db:Session=Depends(get_db)):
    return history(db,status,page,size,review=True)

def unified_history(db,status,page,size,owner=None,review=False):
    # Page the combined timeline, not the two independent source lists.
    structured=select(literal('structured').label('kind'),Contribution.id.label('id'),Contribution.created_at.label('created_at'))
    legacy=select(literal('synopsis').label('kind'),EditSuggestion.id.label('id'),EditSuggestion.created_at.label('created_at'))
    if owner is not None:
        structured=structured.where(Contribution.user_id==owner)
        legacy=legacy.where(EditSuggestion.user_id==owner)
    if review:structured=structured.where(Contribution.status!='draft')
    if status:
        structured=structured.where(Contribution.status==status)
        legacy=legacy.where(EditSuggestion.status==status)
    timeline=union_all(structured,legacy).subquery()
    total=db.scalar(select(func.count()).select_from(timeline))
    rows=db.execute(select(timeline).order_by(timeline.c.created_at.desc(),timeline.c.kind, timeline.c.id.desc()).offset((page-1)*size).limit(size)).all()
    items=[]
    for kind,identity,_ in rows:
        if kind=='structured':
            item=db.get(Contribution,identity)
            if item is not None:items.append({'kind':kind,**output(item)})
        else:
            item=db.get(EditSuggestion,identity)
            if item is None:continue
            author=db.get(User,item.user_id)
            entry=dict(kind=kind,id=item.id,movie_id=item.movie_id,movie_title=item.movie.title,
                       synopsis=item.synopsis,reason=item.reason,status=item.status,
                       author_name=author.username if author else 'Former member',created_at=item.created_at)
            if review and item.status=='pending':entry['current_synopsis']=item.movie.synopsis
            items.append(entry)
    return {'items':items,'total':total}

@router.get('/me/contribution-history')
def my_history(status:Status|None=None,page:int=Query(1,ge=1),size:int=Query(5,ge=1,le=50),user:User=Depends(editor),db:Session=Depends(get_db)):
    return unified_history(db,status,page,size,owner=user.id)

@router.get('/admin/contribution-history')
def admin_history(status:Status|None=None,page:int=Query(1,ge=1),size:int=Query(5,ge=1,le=50),user:User=Depends(admin),db:Session=Depends(get_db)):
    return unified_history(db,status,page,size,review=True)

@router.post('/me/contributions',status_code=201)
def create(payload:CreateDraft,user:User=Depends(editor),db:Session=Depends(get_db)):
    lock_catalog(db);baseline=snapshot(db,payload.entity,payload.target_id)
    if payload.target_id is not None and baseline!=payload.baseline:raise HTTPException(409,'Catalog changed; reload the record before drafting')
    changes=difference(baseline,normalize(payload.entity,payload.changes))
    item=Contribution(user_id=user.id,author_name=user.username,entity=payload.entity,target_id=payload.target_id,baseline=dump(baseline),changes=dump(changes),reason=payload.reason,source_url=payload.source_url)
    db.add(item);db.commit();return output(item)

@router.patch('/me/contributions/{identity}')
def update(identity:int,payload:UpdateDraft,user:User=Depends(editor),db:Session=Depends(get_db)):
    item=get_item(db,identity,user);check(item,payload.version,'draft')
    item.changes=dump(difference(json.loads(item.baseline),normalize(item.entity,payload.changes)))
    item.reason=payload.reason;item.source_url=payload.source_url;touch(item);db.commit();return output(item)

@router.delete('/me/contributions/{identity}',status_code=204)
def delete_draft(identity:int,version:int=Query(...,gt=0),user:User=Depends(editor),db:Session=Depends(get_db)):
    item=get_item(db,identity,user);check(item,version,'draft');db.delete(item);db.commit()

@router.post('/me/contributions/{identity}/submit')
def submit(identity:int,payload:Version,user:User=Depends(editor),db:Session=Depends(get_db)):
    lock_catalog(db);item=get_item(db,identity,user);check(item,payload.version,'draft');assert_current(db,item)
    validate(db,item);item.status='pending';touch(item);db.commit();return output(item)

@router.post('/me/contributions/{identity}/withdraw')
def withdraw(identity:int,payload:Version,user:User=Depends(editor),db:Session=Depends(get_db)):
    item=get_item(db,identity,user);check(item,payload.version,'pending');item.status='withdrawn';touch(item);db.commit();return output(item)

@router.post('/admin/contributions/{identity}/review')
def review(identity:int,payload:Decision,user:User=Depends(admin),db:Session=Depends(get_db)):
    lock_catalog(db);item=get_item(db,identity);check(item,payload.version,'pending')
    if item.user_id==user.id:raise HTTPException(403,'A different administrator must review your contribution')
    if payload.decision=='rejected' and len(payload.note)<5:raise HTTPException(422,'Provide a rejection reason')
    if payload.decision=='approved':
        assert_current(db,item)
        try:item.result_id=apply(db,item)
        except ValidationError as exc:raise HTTPException(422,friendly_validation(exc)) from exc
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        except IntegrityError as exc:raise HTTPException(409,'Catalog relationship conflict') from exc
    item.status=payload.decision;item.reviewer_id=user.id;item.reviewer_name=user.username;item.review_note=payload.note;touch(item)
    try:db.commit()
    except IntegrityError as exc:db.rollback();raise HTTPException(409,'Catalog relationship conflict') from exc
    return output(item)

@router.post('/me/suggestions/{identity}/withdraw')
def withdraw_legacy(identity:int,user:User=Depends(editor),db:Session=Depends(get_db)):
    item=db.scalar(select(EditSuggestion).where(EditSuggestion.id==identity,EditSuggestion.user_id==user.id).with_for_update())
    if not item:raise HTTPException(404,'Suggestion not found')
    if item.status!='pending':raise HTTPException(409,'Suggestion already resolved')
    item.status='withdrawn';db.commit();return {'status':item.status}

@router.get('/editor/credit-labels/{entity}')
def credit_labels(entity:Entity,ids:list[int]=Query(default=[],max_length=500),user:User=Depends(editor),db:Session=Depends(get_db)):
    model,label=(Person,Person.name) if entity=='movie' else (Movie,Movie.title)
    return {str(i):name for i,name in db.execute(select(model.id,label).where(model.id.in_(ids)))}

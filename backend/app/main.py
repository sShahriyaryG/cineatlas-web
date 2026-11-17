from contextlib import asynccontextmanager
from collections import Counter
from datetime import datetime
from typing import Annotated, Literal
from fastapi import FastAPI, Depends, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from .db import Base,engine,get_db
from .models import User,Movie,Rating,Review,Watchlist,EditSuggestion,Report,MovieSource,Genre,MovieGenre,Person,MovieCredit,MovieEnrichmentField
from .catalog import set_movie_genres, parse_genres
from .search import catalog_page, SearchMode, SortMode, GenreMode
from .security import hash_password,verify_password,create_token,revoke_token,current_user,require_role
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(bind=engine) # development convenience; deploy with migrations
    yield
app=FastAPI(title='CineAtlas API',version='0.3.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_credentials=False,allow_methods=['GET','POST','PUT','DELETE','PATCH'],allow_headers=['Authorization','Content-Type'])

class SignUp(BaseModel):
    username: str=Field(min_length=3,max_length=40,pattern=r'^[A-Za-z0-9_]+$')
    email: EmailStr
    password: str=Field(min_length=10,max_length=128)
class Login(BaseModel):
    identifier: str
    password: str
class MovieInput(BaseModel):
    title: str=Field(min_length=1,max_length=240)
    year: int=Field(ge=1888,le=2200)
    genres: str=Field(max_length=4096)
    @field_validator("genres")
    @classmethod
    def valid_genres(cls, value):
        parse_genres(value)
        return value
    synopsis: str=Field(default='',max_length=10000)
    poster_url: str=Field(default='',max_length=600)
    runtime: int | None=Field(default=None,ge=1,le=10000)
    language: str=Field(default='',max_length=100)
    country: str=Field(default='',max_length=100)
class ScoreInput(BaseModel): score:int=Field(ge=1,le=10)
class ReviewInput(BaseModel):
    title:str=Field(min_length=1,max_length=140)
    body:str=Field(min_length=5,max_length=5000)
    spoiler:bool=False
class SuggestionInput(BaseModel):
    synopsis:str=Field(min_length=5,max_length=10000)
    reason:str=Field(min_length=5,max_length=1000)
class ReportInput(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True)
    reason:str=Field(min_length=5,max_length=1000)
class ProfileInput(BaseModel): bio:str=Field(max_length=1000)
class UserRoleInput(BaseModel): role:Literal["member", "editor"]

def safe_user(u): return {'id':u.id,'username':u.username,'role':u.role,'bio':u.bio}
def movie_out(db,m,summary=None):
    avg,count=summary if summary is not None else db.execute(select(func.avg(Rating.score),func.count(Rating.id)).where(Rating.movie_id==m.id)).one()
    return {'id':m.id,'title':m.title,'year':m.year,'genres':[g.name for g in m.genre_entries],'synopsis':m.synopsis,'poster_url':m.poster_url,'runtime':m.runtime,'language':m.language,'country':m.country,'average_rating':round(float(avg),1) if avg is not None else None,'rating_count':count}
def must_movie(db,id):
    m=db.get(Movie,id)
    if not m:raise HTTPException(404,'Movie not found')
    return m

@app.get('/api/health')
def health():return {'status':'ok'}
@app.post('/api/auth/register',status_code=201)
def register(payload:SignUp,db:Session=Depends(get_db)):
    u=User(username=payload.username,email=str(payload.email).lower(),password_hash=hash_password(payload.password))
    db.add(u)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Username or email already exists')
    return {'token':create_token(u.id),'user':safe_user(u)}
@app.post('/api/auth/login')
def login(payload:Login,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(or_(User.email==payload.identifier.lower(),User.username==payload.identifier)))
    if not u or not u.is_active or not verify_password(payload.password,u.password_hash):raise HTTPException(401,'Invalid credentials')
    return {'token':create_token(u.id),'user':safe_user(u)}
@app.get('/api/auth/me')
def me(user:User=Depends(current_user)):return safe_user(user)
@app.post('/api/auth/logout',status_code=204)
def logout(creds:HTTPAuthorizationCredentials=Depends(HTTPBearer()),user:User=Depends(current_user)):
    revoke_token(creds.credentials)
    return Response(status_code=204)
@app.patch('/api/auth/me')
def update_profile(payload:ProfileInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    user.bio=payload.bio;db.commit();return safe_user(user)

@app.get('/api/movies')
def movies(q:str=Query('',max_length=200),mode:SearchMode='title',
           genre:str=Query('',max_length=512),genres:Annotated[list[str]|None,Query(max_length=20)]=None,
           genre_mode:GenreMode='and',year:int|None=Query(None,ge=1888,le=2200),
           year_min:int|None=Query(None,ge=1888,le=2200),year_max:int|None=Query(None,ge=1888,le=2200),
           rating_min:float|None=Query(None,ge=1,le=10),rating_max:float|None=Query(None,ge=1,le=10),
           sort:SortMode='relevance',page:int=Query(1,ge=1,le=100000),size:int=Query(12,ge=1,le=50),
           db:Session=Depends(get_db)):
    labels=[genre,*(genres or [])]
    if any(len(g)>512 or '\x00' in g for g in labels) or '\x00' in q:
        raise HTTPException(422,'Invalid search text or genre label')
    if year_min is not None and year_max is not None and year_min>year_max:
        raise HTTPException(422,'Minimum year must not exceed maximum year')
    if rating_min is not None and rating_max is not None and rating_min>rating_max:
        raise HTTPException(422,'Minimum rating must not exceed maximum rating')
    items,total=catalog_page(db,q=q,mode=mode,genres=labels,genre_mode=genre_mode,year=year,
        year_min=year_min,year_max=year_max,rating_min=rating_min,rating_max=rating_max,sort=sort,page=page,size=size)
    return {'items':[movie_out(db,m,(avg,count)) for m,avg,count in items],'total':total,'page':page,'size':size}
@app.get('/api/genres')
def genres(db:Session=Depends(get_db)):
    return list(db.scalars(select(Genre.name).join(MovieGenre).distinct().order_by(Genre.name)))
@app.get('/api/movies/{movie_id}')
def movie_detail(movie_id:int,db:Session=Depends(get_db)):
    return movie_out(db,must_movie(db,movie_id))
@app.post('/api/movies',status_code=201)
def create_movie(payload:MovieInput,db:Session=Depends(get_db),user:User=Depends(require_role('admin'))):
    m=Movie(**payload.model_dump(exclude={'genres'}));set_movie_genres(db,m,payload.genres);db.add(m);db.commit();db.refresh(m);return movie_out(db,m)
@app.put('/api/movies/{movie_id}')
def update_movie(movie_id:int,payload:MovieInput,db:Session=Depends(get_db),user:User=Depends(require_role('admin'))):
    m=must_movie(db,movie_id)
    for k,v in payload.model_dump(exclude={'genres'}).items():setattr(m,k,v)
    set_movie_genres(db,m,payload.genres)
    db.commit();return movie_out(db,m)
@app.delete('/api/movies/{movie_id}',status_code=204)
def delete_movie(movie_id:int,db:Session=Depends(get_db),user:User=Depends(require_role('admin'))):
    m=must_movie(db,movie_id)
    review_ids=select(Review.id).where(Review.movie_id==movie_id)
    db.query(Report).filter(Report.review_id.in_(review_ids)).delete(synchronize_session=False)
    for model in [Rating,Review,Watchlist,EditSuggestion,MovieSource,MovieEnrichmentField]:db.query(model).filter(model.movie_id==movie_id).delete(synchronize_session=False)
    db.delete(m);db.commit();return Response(status_code=204)

@app.put('/api/movies/{movie_id}/rating')
def rate(movie_id:int,payload:ScoreInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    must_movie(db,movie_id)
    r=db.scalar(select(Rating).where(Rating.user_id==user.id,Rating.movie_id==movie_id))
    if r:r.score=payload.score
    else:db.add(Rating(user_id=user.id,movie_id=movie_id,score=payload.score))
    db.commit();return movie_out(db,must_movie(db,movie_id))
@app.get('/api/movies/{movie_id}/reviews')
def reviews(movie_id:int,db:Session=Depends(get_db)):
    must_movie(db,movie_id)
    items=db.scalars(select(Review).where(Review.movie_id==movie_id,Review.hidden==False).order_by(Review.created_at.desc())).all()
    return [{'id':r.id,'username':r.user.username,'title':r.title,'body':r.body,'spoiler':r.spoiler,'created_at':r.created_at.isoformat()} for r in items]
@app.post('/api/movies/{movie_id}/reviews',status_code=201)
def write_review(movie_id:int,payload:ReviewInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    must_movie(db,movie_id);r=Review(movie_id=movie_id,user_id=user.id,**payload.model_dump());db.add(r);db.commit();return {'id':r.id}
@app.delete('/api/reviews/{review_id}',status_code=204)
def remove_review(review_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    r=db.get(Review,review_id)
    if not r:raise HTTPException(404,'Review not found')
    if user.id!=r.user_id and user.role!='admin':raise HTTPException(403,'Not authorized')
    db.delete(r);db.commit();return Response(status_code=204)
@app.post('/api/reviews/{review_id}/reports',status_code=201)
def report_review(review_id:int,payload:ReportInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not db.get(Review,review_id):raise HTTPException(404,'Review not found')
    r=Report(review_id=review_id,user_id=user.id,reason=payload.reason);db.add(r);db.commit();return {'id':r.id}

@app.get('/api/me/watchlist')
def get_watchlist(user:User=Depends(current_user),db:Session=Depends(get_db)):
    ids=db.scalars(select(Watchlist.movie_id).where(Watchlist.user_id==user.id)).all()
    return [movie_out(db,m) for m in db.scalars(select(Movie).where(Movie.id.in_(ids))).all()]
@app.put('/api/me/watchlist/{movie_id}')
def add_watchlist(movie_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    must_movie(db,movie_id)
    if not db.scalar(select(Watchlist).where(Watchlist.user_id==user.id,Watchlist.movie_id==movie_id)):
        db.add(Watchlist(user_id=user.id,movie_id=movie_id));db.commit()
    return {'saved':True}
@app.delete('/api/me/watchlist/{movie_id}')
def del_watchlist(movie_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    w=db.scalar(select(Watchlist).where(Watchlist.user_id==user.id,Watchlist.movie_id==movie_id))
    if w:db.delete(w);db.commit()
    return {'saved':False}
@app.get('/api/me/recommendations')
def recommendations(user:User=Depends(current_user),db:Session=Depends(get_db)):
    ratings=db.execute(select(Rating,Movie).join(Movie,Movie.id==Rating.movie_id).where(Rating.user_id==user.id)).all()
    weights=Counter()
    for r,m in ratings:
        if r.score>=7:
            for g in m.genre_entries:weights[g.id]+=r.score-5
    seen={r.movie_id for r,m in ratings}
    movies=db.scalars(select(Movie)).all()
    ranked=sorted((m for m in movies if m.id not in seen),key=lambda m:sum(weights[g.id] for g in m.genre_entries),reverse=True)
    return [movie_out(db,m) for m in ranked[:8]]

@app.post('/api/movies/{movie_id}/suggestions',status_code=201)
def suggest(movie_id:int,payload:SuggestionInput,user:User=Depends(require_role('editor','admin')),db:Session=Depends(get_db)):
    must_movie(db,movie_id)
    s=EditSuggestion(movie_id=movie_id,user_id=user.id,**payload.model_dump());db.add(s);db.commit();return {'id':s.id,'status':s.status}
@app.get('/api/me/suggestions')
def my_suggestions(user:User=Depends(require_role('editor','admin')),db:Session=Depends(get_db)):
    items=db.scalars(select(EditSuggestion).where(EditSuggestion.user_id==user.id).order_by(EditSuggestion.id.desc())).all()
    return [{'id':s.id,'movie_id':s.movie_id,'movie_title':s.movie.title,'synopsis':s.synopsis,'reason':s.reason,'status':s.status} for s in items]

@app.get('/api/admin/users')
def list_users(user:User=Depends(require_role('admin')),db:Session=Depends(get_db)):
    items=db.scalars(select(User).order_by(User.username)).all()
    return [{'id':u.id,'username':u.username,'email':u.email,'role':u.role,'is_active':u.is_active} for u in items]

@app.patch('/api/admin/users/{user_id}/role')
def change_user_role(user_id:int,payload:UserRoleInput,user:User=Depends(require_role('admin')),db:Session=Depends(get_db)):
    target=db.get(User,user_id)
    if not target:raise HTTPException(404,'User not found')
    if target.role=='admin':raise HTTPException(409,'Admin accounts must be managed locally')
    if not target.is_active:raise HTTPException(409,'Cannot change an inactive account')
    target.role=payload.role
    db.commit()
    return {'id':target.id,'username':target.username,'role':target.role}

@app.get('/api/admin/suggestions')
def suggestions(user:User=Depends(require_role('admin')),db:Session=Depends(get_db)):
    return [{'id':s.id,'movie_id':s.movie_id,'movie_title':s.movie.title,'current_synopsis':s.movie.synopsis,'submitted_by':db.get(User,s.user_id).username,'synopsis':s.synopsis,'reason':s.reason,'status':s.status} for s in db.scalars(select(EditSuggestion).order_by(EditSuggestion.id.desc()))]
@app.post('/api/admin/suggestions/{id}/{decision}')
def decide(id:int,decision:str,user:User=Depends(require_role('admin')),db:Session=Depends(get_db)):
    if decision not in ('approved','rejected'):raise HTTPException(422,'Invalid decision')
    s=db.get(EditSuggestion,id)
    if not s:raise HTTPException(404,'Suggestion not found')
    if s.status!='pending':raise HTTPException(409,'Already reviewed')
    if decision=='approved':must_movie(db,s.movie_id).synopsis=s.synopsis
    s.status=decision;db.commit();return {'status':s.status}
@app.get('/api/admin/reports')
def reports(user:User=Depends(require_role('admin')),db:Session=Depends(get_db)):
    return [{'id':r.id,'review_id':r.review_id,'review_title':db.get(Review,r.review_id).title,'review_body':db.get(Review,r.review_id).body,'movie_title':db.get(Movie,db.get(Review,r.review_id).movie_id).title,'reported_by':db.get(User,r.user_id).username,'reason':r.reason,'status':r.status} for r in db.scalars(select(Report).order_by(Report.id.desc()))]
@app.post('/api/admin/reports/{id}/{decision}')
def decide_report(id:int,decision:str,user:User=Depends(require_role('admin')),db:Session=Depends(get_db)):
    if decision not in ('dismissed','hidden'):raise HTTPException(422,'Invalid decision')
    r=db.get(Report,id)
    if not r:raise HTTPException(404,'Report not found')
    if r.status!='pending':raise HTTPException(409,'Already reviewed')
    if decision=='hidden':db.get(Review,r.review_id).hidden=True
    r.status=decision;db.commit();return {'status':r.status}
@app.get('/api/admin/stats')
def stats(user:User=Depends(require_role('admin')),db:Session=Depends(get_db)):
    return {'users':db.scalar(select(func.count(User.id))),'movies':db.scalar(select(func.count(Movie.id))),'reviews':db.scalar(select(func.count(Review.id))),'ratings':db.scalar(select(func.count(Rating.id)))}

class PersonInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=240)
    biography: str = Field(default='', max_length=10000)

class CreditInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    person_id: int = Field(gt=0)
    role: Literal['actor', 'director', 'writer', 'producer']
    character: str = Field(default='', max_length=240)

def person_out(person):
    return {'id': person.id, 'name': person.name, 'biography': person.biography}

def credit_out(credit):
    return {'id': credit.id, 'person_id': credit.person_id, 'name': credit.person.name,
            'role': credit.role, 'character': credit.character}

def must_person(db, person_id):
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(404, 'Person not found')
    return person

@app.get('/api/persons')
def list_persons(q: str = '', page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=50), db: Session = Depends(get_db)):
    stmt = select(Person)
    if q:
        stmt = stmt.where(Person.name.icontains(q, autoescape=True))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(Person.name, Person.id).offset((page-1)*size).limit(size))
    return {'items': [person_out(p) for p in items], 'total': total, 'page': page, 'size': size}

@app.get('/api/persons/{person_id}')
def person_detail(person_id: int, db: Session = Depends(get_db)):
    person = must_person(db, person_id)
    credits = db.execute(select(MovieCredit, Movie.title, Movie.year, Movie.poster_url).join(Movie, Movie.id == MovieCredit.movie_id)
                         .where(MovieCredit.person_id == person_id).order_by(Movie.year.desc(), Movie.id, MovieCredit.id))
    return {**person_out(person), 'credits': [dict(movie_id=c.movie_id, title=title, year=year, role=c.role, character=c.character, poster_url=poster_url) for c, title, year, poster_url in credits]}

@app.post('/api/persons', status_code=201)
def create_person(payload: PersonInput, db: Session = Depends(get_db), user: User = Depends(require_role('admin'))):
    person = Person(**payload.model_dump())
    db.add(person); db.commit()
    return person_out(person)

@app.put('/api/persons/{person_id}')
def update_person(person_id: int, payload: PersonInput, db: Session = Depends(get_db), user: User = Depends(require_role('admin'))):
    person = must_person(db, person_id)
    person.name = payload.name; person.biography = payload.biography
    db.commit()
    return person_out(person)

@app.get('/api/movies/{movie_id}/credits')
def movie_credits(movie_id: int, db: Session = Depends(get_db)):
    movie = must_movie(db, movie_id)
    return [credit_out(c) for c in sorted(movie.credits, key=lambda c: (c.role, c.person.name.casefold(), c.id))]

@app.post('/api/movies/{movie_id}/credits', status_code=201)
def create_credit(movie_id: int, payload: CreditInput, db: Session = Depends(get_db), user: User = Depends(require_role('admin'))):
    must_movie(db, movie_id)
    must_person(db, payload.person_id)
    if payload.role != 'actor' and payload.character:
        raise HTTPException(422, 'Only actors may have a character name')
    credit = MovieCredit(movie_id=movie_id, **payload.model_dump())
    db.add(credit)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Credit already exists or catalog changed')
    return credit_out(credit)

@app.delete('/api/movies/{movie_id}/credits/{credit_id}', status_code=204)
def delete_credit(movie_id: int, credit_id: int, db: Session = Depends(get_db), user: User = Depends(require_role('admin'))):
    credit = db.get(MovieCredit, credit_id)
    if not credit or credit.movie_id != movie_id:
        raise HTTPException(404, 'Credit not found')
    db.delete(credit); db.commit()
    return Response(status_code=204)

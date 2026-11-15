from datetime import datetime, timezone
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint, CheckConstraint, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def utcnow(): return datetime.now(timezone.utc)

class User(Base):
    __tablename__='users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40),unique=True,index=True)
    email: Mapped[str] = mapped_column(String(255),unique=True,index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(12),default='member')
    bio: Mapped[str] = mapped_column(Text,default='')
    is_active: Mapped[bool] = mapped_column(Boolean,default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=utcnow)

class Movie(Base):
    __tablename__='movies'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(240),index=True)
    year: Mapped[int] = mapped_column(Integer)
    genres: Mapped[str] = mapped_column(String(255),default='Drama')
    synopsis: Mapped[str] = mapped_column(Text,default='')
    poster_url: Mapped[str] = mapped_column(String(600),default='')
    runtime: Mapped[int | None] = mapped_column(Integer,nullable=True)
    language: Mapped[str] = mapped_column(String(100),default='')
    country: Mapped[str] = mapped_column(String(100),default='')
    legacy_id: Mapped[str | None] = mapped_column(String(50),unique=True,nullable=True)
    __table_args__=(CheckConstraint('year >= 1888 AND year <= 2200',name='valid_year'),)

class Rating(Base):
    __tablename__='ratings'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id',ondelete='CASCADE'))
    score: Mapped[int] = mapped_column(Integer)
    __table_args__=(UniqueConstraint('user_id','movie_id'),CheckConstraint('score BETWEEN 1 AND 10',name='valid_score'))

class Review(Base):
    __tablename__='reviews'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id',ondelete='CASCADE'))
    title: Mapped[str] = mapped_column(String(140))
    body: Mapped[str] = mapped_column(Text)
    spoiler: Mapped[bool] = mapped_column(Boolean,default=False)
    hidden: Mapped[bool] = mapped_column(Boolean,default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=utcnow)
    user: Mapped[User] = relationship()

class Watchlist(Base):
    __tablename__='watchlist'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id',ondelete='CASCADE'))
    __table_args__=(UniqueConstraint('user_id','movie_id'),)

class EditSuggestion(Base):
    __tablename__='edit_suggestions'
    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id'))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    synopsis: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12),default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=utcnow)

class Report(Base):
    __tablename__='reports'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    review_id: Mapped[int] = mapped_column(ForeignKey('reviews.id'))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12),default='pending')

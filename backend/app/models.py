from datetime import date, datetime, timezone
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint, CheckConstraint, DateTime, Text, Boolean, Date, Index, text
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
    genre_entries: Mapped[list['Genre']] = relationship(secondary='movie_genres', lazy='selectin', order_by='Genre.key')
    language_links: Mapped[list['MovieLanguage']] = relationship(lazy='selectin', cascade='all, delete-orphan')
    country_links: Mapped[list['MovieCountry']] = relationship(lazy='selectin', cascade='all, delete-orphan')
    credits: Mapped[list['MovieCredit']] = relationship(back_populates='movie', cascade='all, delete-orphan')
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
    movie: Mapped[Movie] = relationship()
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

class MovieSource(Base):
    """External identity of a catalog record, independent of legacy UUIDs."""
    __tablename__ = 'movie_sources'
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint('source', 'movie_id', name='uq_movie_sources_source_movie'),)


class Genre(Base):
    __tablename__ = 'genres'
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(512), unique=True)
    name: Mapped[str] = mapped_column(String(512))

class MovieGenre(Base):
    __tablename__ = 'movie_genres'
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True)
    genre_id: Mapped[int] = mapped_column(ForeignKey('genres.id', ondelete='CASCADE'), primary_key=True, index=True)

class Person(Base):
    __tablename__ = 'persons'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    biography: Mapped[str] = mapped_column(Text, default='')

class MovieCredit(Base):
    __tablename__ = 'movie_credits'
    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('persons.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(16))
    character: Mapped[str] = mapped_column(String(240), default='')
    movie: Mapped[Movie] = relationship(back_populates='credits')
    person: Mapped[Person] = relationship(lazy='joined')
    __table_args__ = (
        UniqueConstraint('movie_id', 'person_id', 'role', 'character', name='uq_movie_credit'),
        CheckConstraint("role IN ('actor','director','writer','producer','composer','cinematographer','editor','other')", name='valid_credit_role'),
        CheckConstraint("role = 'actor' OR character = ''", name='valid_credit_character'),
    )


class PersonSource(Base):
    """An external identity; names alone are not identity keys."""
    __tablename__ = 'person_sources'
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('persons.id', ondelete='CASCADE'), index=True)
    __table_args__ = (UniqueConstraint('source', 'person_id', name='uq_person_sources_source_person'),)


class MovieEnrichmentField(Base):
    """Import history, not a claim about the current value after manual edits."""
    __tablename__ = 'movie_enrichment_fields'
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True)
    field: Mapped[str] = mapped_column(String(32), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    transport: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    device: Mapped[str] = mapped_column(String(240), default='')
    __table_args__ = (CheckConstraint("transport IN ('cookie','bearer')", name='valid_session_transport'),)


class AuthAttempt(Base):
    __tablename__ = 'auth_attempts'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    bucket: Mapped[int] = mapped_column(Integer, primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    __table_args__ = (CheckConstraint('count >= 1', name='valid_auth_attempt_count'),)


class SecurityEvent(Base):
    __tablename__ = 'security_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


# Optional extensions keep the initial migration's core table definitions intact.
class Language(Base):
    __tablename__ = 'languages'
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(480), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str | None] = mapped_column(String(12), unique=True)


class Country(Base):
    __tablename__ = 'countries'
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(480), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str | None] = mapped_column(String(12), unique=True)


class Tag(Base):
    __tablename__ = 'tags'
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(480), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class MovieLanguage(Base):
    __tablename__ = 'movie_languages'
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True)
    language_id: Mapped[int] = mapped_column(ForeignKey('languages.id', ondelete='RESTRICT'), primary_key=True, index=True)
    kind: Mapped[str] = mapped_column(String(12), primary_key=True)
    language: Mapped[Language] = relationship(lazy='joined')
    __table_args__ = (
        CheckConstraint("kind IN ('original','spoken','unspecified')", name='valid_movie_language_kind'),
        Index('uq_movie_original_language', 'movie_id', unique=True,
              postgresql_where=text("kind = 'original'"), sqlite_where=text("kind = 'original'")),
    )


class MovieCountry(Base):
    __tablename__ = 'movie_countries'
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey('countries.id', ondelete='RESTRICT'), primary_key=True, index=True)
    country: Mapped[Country] = relationship(lazy='joined')


class MovieTag(Base):
    __tablename__ = 'movie_tags'
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey('tags.id', ondelete='RESTRICT'), primary_key=True, index=True)
    tag: Mapped[Tag] = relationship(lazy='joined')


class MovieMetadata(Base):
    __tablename__ = 'movie_metadata'
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True)
    original_title: Mapped[str | None] = mapped_column(String(240))
    release_date: Mapped[date | None] = mapped_column(Date)
    release_status: Mapped[str | None] = mapped_column(String(16))
    trailer_url: Mapped[str | None] = mapped_column(String(600))
    __table_args__ = (CheckConstraint("release_status IN ('released','upcoming','in_production','cancelled')", name='valid_release_status'),)


class MovieAlternativeTitle(Base):
    __tablename__ = 'movie_alternative_titles'
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True)
    key: Mapped[str] = mapped_column(String(480), primary_key=True)
    title: Mapped[str] = mapped_column(String(240))


class MovieCertification(Base):
    __tablename__ = 'movie_certifications'
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey('countries.id', ondelete='RESTRICT'), primary_key=True, index=True)
    rating: Mapped[str] = mapped_column(String(32), primary_key=True)
    country: Mapped[Country] = relationship(lazy='joined')


class MovieSoundtrack(Base):
    __tablename__ = 'movie_soundtracks'
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(240))
    artist: Mapped[str] = mapped_column(String(240), default='')
    composer: Mapped[str] = mapped_column(String(240), default='')
    external_url: Mapped[str | None] = mapped_column(String(600))
    __table_args__ = (CheckConstraint('position >= 0', name='valid_soundtrack_position'),)


class MovieQuote(Base):
    __tablename__ = 'movie_quotes'
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote: Mapped[str] = mapped_column(String(500))
    speaker: Mapped[str] = mapped_column(String(240), default='')
    spoiler: Mapped[bool] = mapped_column(Boolean, default=False)
    source_url: Mapped[str | None] = mapped_column(String(600))
    __table_args__ = (CheckConstraint('position >= 0', name='valid_quote_position'),)


class PersonMetadata(Base):
    __tablename__ = 'person_metadata'
    person_id: Mapped[int] = mapped_column(ForeignKey('persons.id', ondelete='CASCADE'), primary_key=True)
    full_name: Mapped[str | None] = mapped_column(String(240))
    profile_url: Mapped[str | None] = mapped_column(String(600))
    birthday: Mapped[date | None] = mapped_column(Date)
    deathday: Mapped[date | None] = mapped_column(Date)
    birthplace: Mapped[str | None] = mapped_column(String(240))
    __table_args__ = (CheckConstraint('deathday IS NULL OR birthday IS NULL OR deathday >= birthday', name='valid_person_dates'),)


class PersonAlternativeName(Base):
    __tablename__ = 'person_alternative_names'
    person_id: Mapped[int] = mapped_column(ForeignKey('persons.id', ondelete='CASCADE'), primary_key=True)
    key: Mapped[str] = mapped_column(String(480), primary_key=True)
    name: Mapped[str] = mapped_column(String(240))


class PersonNationality(Base):
    __tablename__ = 'person_nationalities'
    person_id: Mapped[int] = mapped_column(ForeignKey('persons.id', ondelete='CASCADE'), primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey('countries.id', ondelete='RESTRICT'), primary_key=True, index=True)
    country: Mapped[Country] = relationship(lazy='joined')


class MovieMetadataOverride(Base):
    """Explicit human edits, including intentional clears; not an audit log."""
    __tablename__ = 'movie_metadata_overrides'
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True)
    field: Mapped[str] = mapped_column(String(32), primary_key=True)
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PersonMetadataOverride(Base):
    __tablename__ = 'person_metadata_overrides'
    person_id: Mapped[int] = mapped_column(ForeignKey('persons.id', ondelete='CASCADE'), primary_key=True)
    field: Mapped[str] = mapped_column(String(32), primary_key=True)
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PersonEnrichmentField(Base):
    """Original import history; does not attest to subsequent manual edits."""
    __tablename__ = 'person_enrichment_fields'
    person_id: Mapped[int] = mapped_column(ForeignKey('persons.id', ondelete='CASCADE'), primary_key=True)
    field: Mapped[str] = mapped_column(String(32), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

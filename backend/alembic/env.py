from logging.config import fileConfig
from alembic import context
from app.db import Base,engine
from app import models
config=context.config
target_metadata=Base.metadata

def run_migrations_offline():
    context.configure(url=str(engine.url),target_metadata=target_metadata,literal_binds=True)
    with context.begin_transaction():context.run_migrations()
def run_migrations_online():
    with engine.connect() as conn:
        context.configure(connection=conn,target_metadata=target_metadata)
        with context.begin_transaction():context.run_migrations()
if context.is_offline_mode():run_migrations_offline()
else:run_migrations_online()

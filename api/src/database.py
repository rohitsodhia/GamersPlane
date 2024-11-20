from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from envs import DATABASE_DATABASE, DATABASE_HOST, DATABASE_PASSWORD, DATABASE_USER

engine = create_engine(
    f"postgresql+psycopg2://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}/{DATABASE_DATABASE}"
)
Session = sessionmaker(bind=engine)

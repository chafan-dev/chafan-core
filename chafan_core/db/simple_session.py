import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

# Format: postgres://<username>:<password>@<hostname>:<port>/<database_name>
# Production database_name is: chafan_prod
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, max_overflow=5,)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

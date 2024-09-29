import os.path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


import logging

from dotenv import load_dotenv  # isort:skip
load_dotenv()  # isort:skip

from chafan_core.db.init_db import init_db
from chafan_core.db.session import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init() -> None:
    db = SessionLocal()
    init_db(db)


def main() -> None:
    logger.info("Creating initial data")
    init()
    logger.info("Initial data created")


if __name__ == "__main__":
    main()

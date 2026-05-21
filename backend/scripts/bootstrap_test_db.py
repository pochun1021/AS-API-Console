from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.base import Base
from db import models  # noqa: F401
from db.session import engine


def main() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    main()

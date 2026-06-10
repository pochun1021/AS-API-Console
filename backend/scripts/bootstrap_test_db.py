from pathlib import Path
import sys

from alembic.config import Config
from alembic import command

# Add parent directory to sys.path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    # Set up Alembic configuration pointing to the 'test_db' section
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("name", "test_db")
    
    # Run migrations to head
    command.upgrade(alembic_cfg, "head")


if __name__ == "__main__":
    main()

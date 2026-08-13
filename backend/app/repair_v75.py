from .migrate_v75 import migrate
from .cleanup_v75_sources import main as cleanup

if __name__ == "__main__":
    migrate()
    cleanup()

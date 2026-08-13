from .database import init_db
from .repository import recalculate_all_scores

if __name__ == '__main__':
    init_db()
    print(recalculate_all_scores())

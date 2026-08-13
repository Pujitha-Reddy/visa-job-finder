from pathlib import Path
from .registry.importer import import_yaml

if __name__ == "__main__":
    path = Path(__file__).resolve().parents[2] / "config" / "employers.yaml"
    print(import_yaml(path))

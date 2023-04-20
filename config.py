import os
import yaml
from pathlib import Path

path = Path(__file__).resolve().parent
with open(os.path.join(path, 'config.yaml'), "r", encoding="utf8") as f:
    try:
        config = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        print(exc)
        exit(1)

config = config

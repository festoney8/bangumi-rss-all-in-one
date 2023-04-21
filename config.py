import os
import yaml
from pathlib import Path
from utils.logger import logger

path = Path(__file__).resolve().parent
with open(os.path.join(path, 'config.yaml'), "r", encoding="utf8") as f:
    try:
        config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.fatal(e)
        exit(1)

config = config

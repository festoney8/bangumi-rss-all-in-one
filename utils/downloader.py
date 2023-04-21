import os
import time
import requests
import shutil
from config import config


def download_file(url: str, abspath: str, filename: str):
    retry_cnt = 0
    ok = False
    while not ok and retry_cnt < config["max_retry"]:
        retry_cnt += 1
        try:
            with requests.get(url, stream=True, timeout=30) as r:
                with open(os.path.join(abspath, filename), 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
            ok = True
            break
        except Exception as e:
            # log
            pass
        if not ok:
            time.sleep(config["wait_sec"])

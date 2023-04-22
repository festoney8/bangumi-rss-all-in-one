import logging
import os

dir_name = os.path.dirname(__file__)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y/%m/%d %H:%M:%S',
    # filename=os.path.join(dir_name, "bangumi_rss.log"),
    # filemode='a+',
    handlers=[
        logging.FileHandler(os.path.join(dir_name, "bangumi_rss.log"), mode='a+'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger()

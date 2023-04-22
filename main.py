import os

from config import config
from sites import Rewrite

tasks = []


def init():
    if not os.path.exists(config["xml_abspath"]):
        os.makedirs(config["xml_abspath"])
    if not os.path.exists("torrent_cache"):
        os.makedirs("torrent_cache")


def register():
    s = config["sites"]
    acgrip = Rewrite(s["acgrip"])
    acgrip.run()
    # tasks.append(Common(s["acgnx"]))
    # tasks.append(Common(s["kisssub"]))
    # tasks.append(Common(s["mikan"]))
    # tasks.append(Common(s["ncraw"]))
    # tasks.append(Dmhy(s["dmhy"]))
    # tasks.append(Nyaa(s["nyaa"]))
    # tasks.append(Rewrite(s["acgrip"]))
    # tasks.append(Rewrite(s["bangumimoe"]))
    #
    # for task in tasks:
    #     task.register_schedule()


if __name__ == '__main__':
    init()
    register()

    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)

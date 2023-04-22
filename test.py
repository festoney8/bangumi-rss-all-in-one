import os
from config import config
from sites import Rewrite, Common, Dmhy, Nyaa

tasks = []


def init():
    if not os.path.exists(config["xml_abspath"]):
        os.makedirs(config["xml_abspath"])
    if not os.path.exists("torrent_cache"):
        os.makedirs("torrent_cache")


def test():
    s = config["sites"]
    tasks.append(Common(s["acgnx"]))
    tasks.append(Common(s["kisssub"]))
    tasks.append(Common(s["mikan"]))
    tasks.append(Common(s["ncraw"]))
    tasks.append(Dmhy(s["dmhy"]))
    tasks.append(Nyaa(s["nyaa"]))
    tasks.append(Rewrite(s["acgrip"]))
    tasks.append(Rewrite(s["bangumimoe"]))

    for task in tasks:
        task.testrun()


if __name__ == '__main__':
    init()
    test()

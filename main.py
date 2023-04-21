from sites import Dmhy, Nyaa, Common, Rewrite
from config import config
import schedule
import time


def register():
    dmhy = Dmhy(config["sites"]["dmhy"])
    acgnx = Common(config["sites"]["acgnx"])
    kisssub = Common(config["sites"]["kisssub"])
    mikan = Common(config["sites"]["mikan"])
    ncraw = Common(config["sites"]["ncraw"])
    nyaa = Nyaa(config["sites"]["nyaa"])
    acgrip = Rewrite(config["sites"]["acgrip"])
    bangumimoe = Rewrite(config["sites"]["bangumimoe"])

    dmhy.register_schedule()
    acgnx.register_schedule()
    kisssub.register_schedule()
    mikan.register_schedule()
    ncraw.register_schedule()
    nyaa.register_schedule()
    acgrip.register_schedule()
    bangumimoe.register_schedule()


if __name__ == '__main__':
    register()

    while True:
        schedule.run_pending()
        time.sleep(1)

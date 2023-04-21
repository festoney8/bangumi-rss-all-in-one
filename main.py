from sites import Dmhy, Nyaa, Common, Rewrite
from config import config
import schedule
import time


def register():
    s = config["sites"]
    dmhy = Dmhy(s["dmhy"])
    acgnx = Common(s["acgnx"])
    kisssub = Common(s["kisssub"])
    mikan = Common(s["mikan"])
    ncraw = Common(s["ncraw"])
    nyaa = Nyaa(s["nyaa"])
    acgrip = Rewrite(s["acgrip"])
    bangumimoe = Rewrite(s["bangumimoe"])

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

import calendar
import os
import time
from datetime import datetime
from html import unescape

import feedparser
import schedule
from rfeed import *

from utils.downloader import download
from utils.logger import logger
from utils.magnet import *


class Torrent:
    def __init__(self, title: str, pubdate: datetime, link="", infohash="", torrent_url=""):
        self.title = title
        self.pubdate = pubdate
        self.link = link
        self.infohash = infohash
        self.torrent_url = torrent_url


class Site:
    """
    baseclass, the main process is func `run()`
    the `parse()` process is according to each site, it's override by subclass
    """

    def __init__(self, site_config: dict):
        self.enable = site_config["enable"]
        self.rss_url = site_config["rss_url"]
        self.refresh_interval = site_config["refresh_interval"]
        self.local_xml_file = site_config["local_xml_file"]
        self.taskname = self.local_xml_file.replace(".xml", "")

        self.single_feed = None
        self.single_rss = None
        self.torrents: [Torrent] = []
        self.map_infohash = {}

    def fetch(self):
        """
        fetch rss by url and try to parse it using feedparser
        :return:
        """
        ok = False
        retry_cnt = 0
        while not ok and retry_cnt < config["max_retry"]:
            retry_cnt += 1
            try:
                self.single_feed = feedparser.parse(self.rss_url, agent=config["useragent"])
                logger.debug(f"task {self.taskname} fetch feed, http status {self.single_feed.status}")
                # http status code, usually 200 or 301
                if self.single_feed.status < 400:
                    ok = True
                    break
                elif self.single_feed.status == 429:
                    logger.error(f"task {self.taskname} fetch feed failed, "
                                 f"too many requests, your IP may in blacklist")
                    break
                else:
                    logger.error(f"task {self.taskname} fetch feed failed, http status {self.single_feed.status}")
            except Exception as e:
                logger.error(f"task {self.taskname} fetch feed failed")
                logger.error(e)
                pass
            if not ok:
                time.sleep(config["fetch_wait_sec"])

    def parse(self):
        """
        impl in each subclass
        extract torrent info from rss feed self.single_feed
        torrent info will save to self.torrents

        Bugfix:
        The pubDate in rss v2.0 is RFC822 format, such as
        `Wed, 19 Apr 2023 16:49:20 GMT` or `Mon, 24 Apr 2023 03:15:00 +0800`.
        feedparser `entries[i].published_parsed` auto convert it to time.struct_time in GMT.
        rfeed need datetime to generate feed item.

        `datetime.fromtimestamp(time.mktime())` can convert struct_time to datetime,
        but `time.mktime()` is according to system timezone.
        So if rss pubdate and system use different timezone, `time.mktime()` will cause pubdate mistake.
        Example:
            System timezone = GMT+8
            GMT pubDate -> GMT published_parsed -> mktime() -> wrong timestamp(+8h) -> rfeed wrong pubdate
        After `merge()` serval times, the pubdate moving will affect more.

        Solution: use calendar.timegm() instead of time.mktime()
        Ref: https://stackoverflow.com/questions/2956886
        :return:
        """
        pass

    def localize(self):
        """
        simplify the rss content, only keep title, pubDate, link, enclosure
        save single site rss xml file locally
        :return:
        """
        if not self.torrents:
            return
        # generate local rss
        items = []
        for t in self.torrents:
            item = Item(
                title=t.title,
                link=t.link,
                # rfeed need GMT input
                pubDate=datetime.utcfromtimestamp(calendar.timegm(t.pubdate)),
                enclosure=Enclosure(url=infohash_to_magnet(t.infohash), type="application/x-bittorrent", length=0),
            )
            items.append(item)
        self.single_rss = Feed(
            title=f"{self.taskname} rss",
            link=self.rss_url,
            description="Generate by bangumi rss all-in-one",
            lastBuildDate=datetime.utcnow(),
            items=items
        )
        # save xml file
        fpath = os.path.join(config["xml_abspath"], self.local_xml_file)
        with open(fpath, "w", encoding="utf8") as f:
            f.write(self.single_rss.rss())
            logger.debug(f"task {self.taskname} save to disk")

    def merge(self):
        """
        merge single site rss to total rss
        de-duplicate torrents and generate new total rss
        :return:
        """
        total_xml = os.path.join(config["xml_abspath"], config["total_xml_filename"])
        # if total rss file not exist, init it
        if not os.path.exists(total_xml):
            with open(total_xml, "w", encoding="utf8") as f:
                f.write(self.single_rss.rss())
                logger.debug(f"task {self.taskname} init total rss, save to disk")
            return

        # merge single site rss and total rss
        feed = feedparser.parse(total_xml)
        if not feed.entries:
            with open(total_xml, "w", encoding="utf8") as f:
                f.write(self.single_rss.rss())
                logger.debug(f"task {self.taskname} init, save to disk")
            return
        for e in feed.entries:
            self.torrents.append(Torrent(
                title=e.title,
                link=e.link,
                pubdate=e.published_parsed,
                infohash=detect_infohash(e.links[1].href),
            ))

        # de-duplicate torrents by infohash
        tmp = {}
        for t in self.torrents:
            tmp[t.infohash] = t
        self.torrents = tmp.values()

        # sort torrents by pubdate and limit amount
        self.torrents = sorted(self.torrents, key=lambda x: x.pubdate, reverse=True)
        self.torrents = self.torrents[:config["max_items"]]

        # generate all-in-one rss xml
        items = []
        for t in self.torrents:
            items.append(Item(
                title=t.title,
                # rfeed need GMT input
                pubDate=datetime.utcfromtimestamp(calendar.timegm(t.pubdate)),
                link=t.link,
                enclosure=Enclosure(url=infohash_to_magnet(t.infohash),
                                    length=0, type="application/x-bittorrent"),
            ))
        total_rss = Feed(
            title="bangumi rss",
            link="",
            description="Generate by bangumi rss all in one",
            lastBuildDate=datetime.utcnow(),
            items=items
        )
        fpath = os.path.join(config["xml_abspath"], config["total_xml_filename"])
        with open(fpath, "w", encoding="utf8") as f:
            f.write(total_rss.rss())
            logger.debug(f"task {self.taskname} merge to total, save to disk")

    def run(self):
        """
        main process of the project
        fetch, parse, localize and merge
        :return:
        """
        logger.info(f"########### task {self.taskname} start ###########")
        self.fetch()
        if not self.single_feed or not self.single_feed.entries:
            logger.error(f"fetch {self.taskname} failed")
            return
        try:
            self.parse()
            logger.info(f"parse {self.taskname}")
        except Exception as e:
            logger.error(f"task {self.taskname} parse failed")
            logger.error(e)
            return
        try:
            self.localize()
            logger.info(f"localize {self.taskname}")
        except Exception as e:
            logger.error(f"task {self.taskname} localize failed")
            logger.error(e)
            return
        try:
            self.merge()
            logger.info(f"merge {self.taskname}")
        except Exception as e:
            logger.error(f"task {self.taskname} merge failed")
            logger.error(e)
            return

    def testrun(self):
        """
        run immediately
        :return:
        """
        if self.enable:
            self.run()

    def register_schedule(self):
        """
        register cron job
        :return:
        """
        if self.enable:
            schedule.every(self.refresh_interval).minutes.do(self.run)
            logger.info(f"register schedule {self.taskname}")


class Common(Site):
    """
    Common can parse [acgnx, kisssub, ncraw, mikan]
    """

    def parse(self):
        self.torrents = self.torrents[:0]
        entries = self.single_feed.entries
        for e in entries:
            infohash = detect_infohash(e.link)
            self.torrents.append(Torrent(
                title=unescape(e.title),
                pubdate=e.published_parsed,
                link=e.link,
                infohash=infohash))
            logger.debug(f"task {self.taskname} parse torrent: {infohash}")


class Dmhy(Site):
    def parse(self):
        self.torrents = self.torrents[:0]
        entries = self.single_feed.entries
        for e in entries:
            infohash = detect_infohash(e.links[1].href)
            self.torrents.append(Torrent(
                title=unescape(e.title),
                pubdate=e.published_parsed,
                link=e.link,
                infohash=infohash))
            logger.debug(f"task {self.taskname} parse torrent: {infohash}")


class Nyaa(Site):
    def parse(self):
        self.torrents = self.torrents[:0]
        entries = self.single_feed.entries
        for e in entries:
            self.torrents.append(Torrent(
                title=unescape(e.title),
                pubdate=e.published_parsed,
                link=e.id,
                infohash=e.nyaa_infohash))
            logger.debug(f"task {self.taskname} parse torrent: {e.nyaa_infohash}")


class Rewrite(Site):
    """
    Rewrite can parse [Acgrip, Bangumimoe]
    cannot find info_hash from these sites, so have to convert .torrent file to magnet
    """

    def parse(self):
        self.torrents = self.torrents[:0]
        entries = self.single_feed.entries
        for e in entries:
            torrent_url = e.links[1].href
            self.torrents.append(Torrent(
                title=unescape(e.title),
                pubdate=e.published_parsed,
                link=e.link,
                torrent_url=torrent_url))

        # convert torrent to infohash
        for t in self.torrents:
            # read infohash from map cache
            infohash = self.map_infohash.get(t.link)
            if not infohash:
                # download and parse torrent file
                # get infohash then update map cache
                t_name = t.torrent_url.split("/")[-1]
                t_file = os.path.join("torrent_cache", t_name)
                # if torrent exist, skip download
                if os.path.exists(t_file):
                    ok = True
                else:
                    ok = download(t.torrent_url, t_file)
                    time.sleep(config["download_wait_sec"])
                if ok:
                    logger.debug(f"download torrent {t.torrent_url}")
                    try:
                        infohash = get_torrent_infohash(t_file)
                        self.map_infohash[t.link] = infohash
                        logger.debug(f"get torrent {t_file} info hash, {infohash}")
                    except Exception as e:
                        logger.error(f"get torrent {t_file} info hash failed")
                        logger.error(e)
            if infohash:
                t.infohash = infohash
            logger.debug(f"task {self.taskname} parse torrent: {infohash}")

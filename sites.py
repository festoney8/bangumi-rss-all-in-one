import os
import time
import urllib.parse
import schedule
import feedparser
from datetime import datetime
from rfeed import *
from utils.downloader import download
from utils.magnet import *
from utils.logger import logger
from config import config


class Torrent:
    def __init__(self, title: str, pubdate: datetime, link="", infohash="", torrent_url=""):
        self.title = title
        self.pubdate = pubdate
        self.link = link
        self.infohash = infohash
        self.torrent_url = torrent_url


class Site:
    def __init__(self, site_config: dict):
        self.enable = site_config["enable"]
        self.rss_url = site_config["rss_url"]
        self.refresh_interval = site_config["refresh_interval"]
        self.local_xml_file = site_config["local_xml_file"]
        self.task_name = self.local_xml_file.replace(".xml", "")

        self.single_feed = None
        self.single_rss = None
        self.torrents: [Torrent] = []
        self.map_infohash: dict = {}

    def fetch(self):
        ok = False
        retry_cnt = 0
        while not ok and retry_cnt < config["max_retry"]:
            retry_cnt += 1
            try:
                self.single_feed = feedparser.parse(self.rss_url, agent=config["useragent"])
                ok = True
                break
            except Exception as e:
                logger.exception(f"fetch rss {self.rss_url} failed, try {retry_cnt} times")
                logger.exception(e)
                pass
            if not ok:
                time.sleep(config["wait_sec"])

    def parse(self):
        # impl in subclass, torrent info will save to self.torrents
        pass

    def localize(self):
        # keep title, pubDate, link, enclosure
        if not self.torrents:
            return
        # generate local rss
        items = []
        for t in self.torrents:
            item = Item(
                title=t.title,
                link=t.link,
                pubDate=datetime.fromtimestamp(time.mktime(t.pubdate)),
                enclosure=Enclosure(url=infohash_to_magnet(t.infohash), type="application/x-bittorrent", length=0),
            )
            items.append(item)
        self.single_rss = Feed(
            title=f"RSS Feed {self.local_xml_file}",
            link=self.rss_url,
            description="Generate by bangumi rss all in one",
            lastBuildDate=datetime.now(),
            items=items
        )
        # save xml file
        fpath = os.path.join(config["xml_abspath"], self.local_xml_file)
        with open(fpath, "w", encoding="utf8") as f:
            f.write(self.single_rss.rss())
            logger.info(f"task {self.task_name} save to disk")

    def merge(self):
        total_xml = os.path.join(config["xml_abspath"], config["total_xml_filename"])
        # if total rss file not exist, init it
        if not os.path.exists(total_xml):
            with open(total_xml, "w", encoding="utf8") as f:
                f.write(self.single_rss.rss())
                logger.debug(f"task {self.task_name} init, save to disk")
            return

        # merge single site rss and total rss
        feed = feedparser.parse(total_xml)
        if not feed.entries:
            with open(total_xml, "w", encoding="utf8") as f:
                f.write(self.single_rss.rss())
                logger.debug(f"task {self.task_name} init, save to disk")
            return
        for e in feed.entries:
            self.torrents.append(Torrent(
                title=e.title,
                link=e.link,
                pubdate=e.published_parsed,
                infohash=e.links[1].href,
            ))

        # de-duplicate torrents by magnet
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
            url = t.magnet
            if not url:
                url = t.torrent_url
            items.append(Item(
                title=t.title,
                pubDate=datetime.fromtimestamp(time.mktime(t.pubdate)),
                link=t.link,
                enclosure=Enclosure(url=url, length=1, type="application/x-bittorrent"),
            ))
        total_rss = Feed(
            title="bangumi rss",
            link="",
            description="Generate by bangumi rss all in one",
            lastBuildDate=datetime.now(),
            items=items
        )
        fpath = os.path.join(config["xml_abspath"], config["total_xml_filename"])
        with open(fpath, "w", encoding="utf8") as f:
            f.write(total_rss.rss())
            logger.debug(f"task {self.task_name} merge to total, save to disk")

    def run(self):
        self.fetch()
        if not self.single_feed or not self.single_feed.entries:
            logger.error(f"fetch {self.task_name} failed")
            return
        try:
            self.parse()
            logger.info(f"parse {self.task_name}")
        except Exception as e:
            logger.error(f"task {self.task_name} parse failed")
            logger.error(e)
            return
        try:
            self.localize()
            logger.info(f"localize {self.task_name}")
        except Exception as e:
            logger.error(f"task {self.task_name} localize failed")
            logger.error(e)
            return
        try:
            self.merge()
            logger.info(f"merge {self.task_name}")
        except Exception as e:
            logger.error(f"task {self.task_name} merge failed")
            logger.error(e)
            return

    def register_schedule(self):
        if self.enable:
            schedule.every(self.refresh_interval).minutes.do(self.run)
            logger.info(f"register schedule {self.task_name}")


# class Common can parse [acgnx, kisssub, ncraw, mikan]
class Common(Site):
    def parse(self):
        self.torrents = self.torrents[:0]
        entries = self.single_feed.entries
        for e in entries:
            infohash = detect_infohash(e.link)
            self.torrents.append(Torrent(
                title=e.title,
                pubdate=e.published_parsed,
                link=e.link,
                infohash=infohash))


class Dmhy(Site):
    def parse(self):
        self.torrents = self.torrents[:0]
        entries = self.single_feed.entries
        for e in entries:
            infohash = detect_infohash(e.links[1].href)
            self.torrents.append(Torrent(
                title=e.title,
                pubdate=e.published_parsed,
                link=e.link,
                infohash=infohash))


class Nyaa(Site):
    def parse(self):
        self.torrents = self.torrents[:0]
        entries = self.single_feed.entries
        for e in entries:
            self.torrents.append(Torrent(
                title=e.title,
                pubdate=e.published_parsed,
                link=e.id,
                infohash=e.nyaa_infohash))


# class Rewrite can parse [Acgrip, Bangumimoe]
class Rewrite(Site):
    def parse(self):
        self.torrents = self.torrents[:0]
        entries = self.single_feed.entries
        for e in entries:
            torrent_url = e.links[1].href
            self.torrents.append(Torrent(
                title=e.title,
                pubdate=e.published_parsed,
                link=e.link,
                torrent_url=torrent_url))

        # convert torrent to magnet
        for t in self.torrents:
            # read infohash from map cache
            infohash = self.map_infohash[t.link]
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

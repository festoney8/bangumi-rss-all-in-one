import os
import re
import time
import urllib.parse
import schedule
import feedparser
from datetime import datetime
from rfeed import *
from utils.downloader import download_file
from config import config


class Torrent:
    def __init__(self, title: str, pubdate: datetime, link="", magnet="", torrent_url=""):
        self.title = title
        self.pubdate = pubdate
        self.link = link
        self.magnet = magnet
        self.torrent_url = torrent_url


class Site:
    single_feed: feedparser.FeedParserDict
    single_rss: rfeed.Feed
    torrents: [Torrent]
    map_torrent_magnet: {}

    def __init__(self, enable: bool, rss_url: str, refresh_interval: int,
                 local_xml_filename: str):
        self.enable = enable
        self.rss_url = rss_url
        self.refresh_interval = refresh_interval
        self.local_xml_filename = local_xml_filename

    def fetch_rss(self) -> bool:
        ok = False
        retry_cnt = 0
        while not ok and retry_cnt < config["max_retry"]:
            retry_cnt += 1
            try:
                self.single_feed = feedparser.parse(self.rss_url, agent=config["useragent"])
                ok = True
                break
            except Exception as e:
                pass
            if not ok:
                time.sleep(config["wait_sec"])
        return ok

    def parse_rss(self):
        # impl in subclass, torrent info will save to self.torrents
        pass

    def localize_rss(self):
        # keep title, pubDate, link, enclosure
        if not self.torrents:
            return
        # generate local rss
        items = []
        for t in self.torrents:
            url = t.magnet
            items.append(Item(
                title=t.title,
                link=t.link,
                pubDate=t.pubdate,
                enclosure=Enclosure(url=url, type="application/x-bittorrent", length=0),
            ))
        self.single_rss = Feed(
            title="dmhy rss",
            link=self.rss_url,
            description="Generate by bangumi rss all in one",
            lastBuildDate=datetime.now(),
            items=items
        )
        # save xml file
        fpath = os.path.join(config["xml_abspath"], self.local_xml_filename)
        with open(fpath, "w", encoding="utf8") as f:
            f.write(self.single_feed.rss())

    def merge_rss(self):
        total_xml = os.path.join(config["xml_abspath"], config["total_xml_filename"])
        # if total rss file not exist, init it
        if not os.path.exists(total_xml):
            with open(total_xml, "w", encoding="utf8") as f:
                f.write(self.single_rss.rss())
            return

        # merge single site rss and total rss
        feed = feedparser.parse(total_xml)
        for e in feed.entries:
            t = Torrent(
                title=e.title,
                link=e.link,
                pubdate=datetime.fromtimestamp(time.mktime(e.published_parsed)),
            )
            url = e.links[1].href
            if url.startsWith("magnet"):
                t.magnet = url
            elif url.endsWith(".torrent"):
                t.torrent_url = url
            self.torrents.append(t)
        # de-duplicate torrents by magnet
        s = set()
        tmp = []

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
                pubDate=datetime.fromtimestamp(time.mktime(t.published_parsed)),
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

    def run(self):
        ok = self.fetch_rss()
        if ok:
            self.parse_rss()
            self.cache_torrents()
            self.localize_rss()
            self.merge_rss()

    def register_schedule(self):
        if self.enable:
            schedule.every(self.refresh_interval).minutes.do(self.run)


class Dmhy(Site):
    magnet_regex = re.compile(r"magnet:?xt=urn:btih:[0-9A-Z]{32}")

    def parse_rss(self):
        self.torrents = self.torrents[:0]
        entries = self.single_feed.entries
        for e in entries:
            # add trackers to magnet and urlencoded it
            magnet = e.links[1].href
            magnet = re.findall(self.magnet_regex, magnet)[0]
            magnet = "&tr=".join([magnet] + config["trackers"])
            magnet = urllib.parse.quote_plus(magnet)
            self.torrents.append(Torrent(
                title=e.title,
                pubdate=e.published_parsed,
                link=e.link,
                magnet=magnet))


# class Acgrip(Site):
#     def parse_rss(self):
#         def _cache_torrents(self):
#             for t in self.torrents:
#                 if t.torrent_url.endsWith(".torrent"):
#                     t_name = t.torrent_url.split("/")[-1]
#                     abspath = os.path.join(config["torrent_abspath"], self.torrent_cache_relpath)
#                     # skip when torrent exist
#                     if not os.path.exists(os.path.join(abspath, t_name)):
#                         download_file(t.torrent_url, abspath, t_name)
#
#         self.torrents = self.torrents[:0]
#         entries = self.single_feed.entries
#         for e in entries:
#             # add trackers to magnet and urlencoded it
#             magnet = e.links[1].href
#             magnet = re.findall(self.magnet_regex, magnet)[0]
#             magnet = "&tr=".join([magnet] + config["trackers"])
#             magnet = urllib.parse.quote_plus(magnet)
#             self.torrents.append(Torrent(
#                 title=e.title,
#                 pubdate=e.published_parsed,
#                 link=e.link,
#                 magnet=magnet))

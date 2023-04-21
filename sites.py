import os
import re
import time
import urllib.parse
from datetime import datetime

import feedparser
from rfeed import *
import schedule
from utils.downloader import download_file
from config import config


class Site:
    single_feed: feedparser.FeedParserDict
    items: [rfeed.Item]
    single_rss: rfeed.Feed

    def __init__(self, enable: bool, rss_url: str, refresh_interval: int,
                 save_torrent: bool, local_xml_filename: str):
        self.enable = enable
        self.rss_url = rss_url
        self.refresh_interval = refresh_interval
        self.save_torrent = save_torrent
        self.local_xml_filename = local_xml_filename

    def cache_torrents(self, torrents: dict):
        if not self.save_torrent:
            return
        for t_url, t_name in torrents:
            if os.path.exists(os.path.join(config["torrent_abspath"], t_name)):
                ok = download_file(t_url, config["torrent_abspath"], t_name)

    def fetch_rss(self) -> bool:
        ok = False
        retry_cnt = 0
        while not ok and retry_cnt < config["max_retry"]:
            try:
                self.feed = feedparser.parse(self.rss_url, agent=config["useragent"])
                ok = True
                break
            except Exception as e:
                pass
            if not ok:
                time.sleep(config["wait_sec"])
        return ok

    def localize_rss(self):
        # impl in subclass
        pass

    def merge_rss(self):
        total_xml = os.path.join(config["xml_abspath"], config["total_xml_filename"])
        # if total rss file not exist, init it
        if not os.path.exists(total_xml):
            with open(total_xml, "w", encoding="utf8") as f:
                f.write(self.single_rss.rss())
            return
        # merge single site rss to total
        feed = feedparser.parse(total_xml)
        for e in feed.entries:
            magnet = e.links[1].href
            self.items.append(Item(
                title=e.title,
                link=e.link,
                enclosure=Enclosure(url=magnet, length=1, type="application/x-bittorrent"),
                pubDate=datetime.fromtimestamp(time.mktime(e.published_parsed))
            ))
        # sort by pubdate
        self.items = sorted(self.items, key=lambda x: x.pubDate, reverse=True)
        # limit items
        self.items = self.items[:config["max_items"]]
        # generate all-in-one rss feed
        total_rss = Feed(
            title="dmhy rss",
            link=self.rss_url,
            description="Generate by bangumi rss all in one",
            lastBuildDate=datetime.now(),
            items=self.items
        )
        fpath = os.path.join(config["xml_abspath"], config["total_xml_filename"])
        with open(fpath, "w", encoding="utf8") as f:
            f.write(total_rss.rss())

    def run(self):
        ok = self.fetch_rss()
        if ok:
            # beauty rss and cache the torrents
            self.localize_rss()
            # merge single site rss to total rss
            self.merge_rss()

    def register_schedule(self):
        if self.enable:
            schedule.every(self.refresh_interval).minutes.do(self.run)


class Dmhy(Site):
    magnet_regex = re.compile(r"magnet:?xt=urn:btih:[0-9A-Z]{32}")

    # keep title, pubDate, link, enclosure
    def localize_rss(self):
        if not self.feed:
            return
        # parse rss and generate local feed
        self.items = self.items[:0]
        entries = self.feed.entries
        for e in entries:
            # add trackers to magnet and urlencoded it
            magnet = e.links[1].href
            magnet = re.findall(self.magnet_regex, magnet)[0]
            magnet = "&tr=".join([magnet] + config["trackers"])
            magnet = urllib.parse.quote_plus(magnet)
            self.items.append(Item(
                title=e.title,
                link=e.link,
                enclosure=Enclosure(url=magnet, length=1, type="application/x-bittorrent"),
                # convert time.struct_time to datetime.datetime
                pubDate=datetime.fromtimestamp(time.mktime(e.published_parsed))
            ))
        self.single_rss = Feed(
            title="dmhy rss",
            link=self.rss_url,
            description="Generate by bangumi rss all in one",
            lastBuildDate=datetime.now(),
            items=self.items
        )
        # save xml file
        fpath = os.path.join(config["xml_abspath"], self.local_xml_filename)
        with open(fpath, "w", encoding="utf8") as f:
            f.write(self.single_feed.rss())

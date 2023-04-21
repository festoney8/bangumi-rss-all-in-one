import os
import re
import time
import base64
import urllib.parse
import schedule
import feedparser
import binascii
from datetime import datetime
from rfeed import *
from utils.downloader import download
from utils.parse_torrent import get_info_hash
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
    map_info_hash: {}

    def __init__(self, enable: bool, rss_url: str, refresh_interval: int,
                 local_xml_filename: str, convert_magnet: bool, cache_relpath: str):
        self.enable = enable
        self.rss_url = rss_url
        self.refresh_interval = refresh_interval
        self.local_xml_filename = local_xml_filename
        self.convert_magnet = convert_magnet
        self.cache_relpath = cache_relpath

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
            items.append(Item(
                title=t.title,
                link=t.link,
                pubDate=t.pubdate,
                enclosure=Enclosure(url=t.magnet, type="application/x-bittorrent", length=0),
            ))
        self.single_rss = Feed(
            title=f"RSS Feed {self.local_xml_filename}",
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
        tmp = {}
        regex = re.compile(r"[0-9a-f]{40}")
        for t in self.torrents:
            magnet = regex.findall(t.magnet)[0]
            tmp[magnet] = t
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
            try:
                self.parse_rss()
                self.localize_rss()
                self.merge_rss()
            except Exception as e:
                pass

    def register_schedule(self):
        if self.enable:
            schedule.every(self.refresh_interval).minutes.do(self.run)


# class Common can parse [acgnx, kisssub, ncraw, mikan]
class Common(Site):
    regex = re.compile(r"[0-9a-f]{40}")

    def parse_rss(self):
        self.torrents = self.torrents[:0]
        entries = self.single_feed.entries
        for e in entries:
            # add trackers to magnet and urlencoded it
            magnet = "magnet:?xt=urn:btih:" + re.findall(self.regex, e.link)[0]
            magnet = "&tr=".join([magnet] + config["trackers"])
            magnet = urllib.parse.quote_plus(magnet)
            self.torrents.append(Torrent(
                title=e.title,
                pubdate=e.published_parsed,
                link=e.link,
                magnet=magnet))


class Dmhy(Site):
    # dmhy use base32 magnet
    regex = re.compile(r"[0-9A-Z]{32}")

    def parse_rss(self):
        self.torrents = self.torrents[:0]
        entries = self.single_feed.entries
        for e in entries:
            magnet = e.links[1].href
            # convert DMHY base32 magnet to hex magnet
            base32_bytes = re.findall(self.regex, magnet)[0]
            base64_bytes = base64.b32decode(base32_bytes.encode('ascii'))
            hex_bytes = binascii.hexlify(base64_bytes)
            magnet = "magnet:?xt=urn:btih:" + hex_bytes.decode('ascii')
            # add trackers and urlencoded it
            magnet = "&tr=".join([magnet] + config["trackers"])
            magnet = urllib.parse.quote_plus(magnet)
            self.torrents.append(Torrent(
                title=e.title,
                pubdate=e.published_parsed,
                link=e.link,
                magnet=magnet))


class Nyaa(Site):
    def parse_rss(self):
        self.torrents = self.torrents[:0]
        entries = self.single_feed.entries
        for e in entries:
            magnet = "magnet:?xt=urn:btih:" + e.nyaa_infohash
            magnet = "&tr=".join([magnet] + config["trackers"])
            magnet = urllib.parse.quote_plus(magnet)
            self.torrents.append(Torrent(
                title=e.title,
                pubdate=e.published_parsed,
                link=e.id,
                magnet=magnet))


# class Rewrite can parse [Acgrip, Bangumimoe]
class Rewrite(Site):
    def parse_rss(self):
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
            # read info_hash from map cache
            info_hash = self.map_info_hash[t.link]
            if not info_hash:
                # download and parse torrent file
                # get info_hash then write map cache
                t_name = t.torrent_url.split("/")[-1]
                t_file = os.path.join("torrent_cache", t_name)
                # if torrent exist, skip download
                if os.path.exists(t_file):
                    ok = True
                else:
                    ok = download(t.torrent_url, t_file)
                if ok:
                    info_hash = get_info_hash(t_file)
                    self.map_info_hash[t.link] = info_hash
            if info_hash:
                t.magnet = "magnet:?xt=urn:btih:" + info_hash
                t.magnet = "&tr=".join([t.magnet] + config["trackers"])
                t.magnet = urllib.parse.quote_plus(t.magnet)

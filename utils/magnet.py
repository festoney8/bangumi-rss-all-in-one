import base64
import binascii
import hashlib
import re

import bencodepy

from config import config


def get_torrent_infohash(filepath: str):
    torrent = bencodepy.decode_from_file(filepath)
    info = torrent[b"info"]
    info_str = bencodepy.encode(info)
    return hashlib.sha1(info_str).hexdigest()


def detect_infohash(href: str) -> str:
    regex_base32_magnet = re.compile(r"[0-9A-Z]{32}")
    regex_hex_magnet = re.compile(r"[0-9a-f]{40}")

    if regex_hex_magnet.findall(href):
        return regex_hex_magnet.findall(href)[0]
    if regex_base32_magnet.findall(href):
        b32_magnet = regex_base32_magnet.findall(href)[0]
        # convert base32 magnet to hex magnet
        base64_bytes = base64.b32decode(b32_magnet.encode('ascii'))
        hex_bytes = binascii.hexlify(base64_bytes)
        return hex_bytes.decode('ascii')
    return ""


def infohash_to_magnet(infohash: str) -> str:
    if config["add_trackers_to_magnet"]:
        return "magnet:?xt=urn:btih:" + "&tr=".join([infohash] + config["trackers"])
    return "magnet:?xt=urn:btih:" + infohash

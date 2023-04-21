import bencodepy
import hashlib


def get_info_hash(filepath):
    torrent = bencodepy.decode_from_file(filepath)
    info = torrent[b"info"]
    info_str = bencodepy.encode(info)
    return hashlib.sha1(info_str).hexdigest()

"""Syntactic public URL validation; never resolves or fetches a URL."""
from ipaddress import ip_address
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import re

def public_url(raw):
    if not raw or len(raw)>2048 or re.search(r'[\s\\\x00-\x1f]',raw):
        return None
    try:
        url=urlsplit(raw)
        host=(url.hostname or '').lower().removeprefix('www.')
        if url.scheme not in ('https','http') or url.username or url.password or not host or url.port not in (None,80,443):
            return None
        if host in ('localhost',) or host.endswith(('.localhost','.local','.internal','.example','.test','.invalid')) or '.' not in host:
            return None
        try:
            if not ip_address(host).is_global:return None
        except ValueError:
            if re.fullmatch(r'[\d.]+',host):return None
        query=sorted((k,v) for k,v in parse_qsl(url.query) if not re.match(r'^(utm_|fbclid$|gclid$|igsh|tt_from$)',k,re.I))
        return urlunsplit((url.scheme,host,url.path.rstrip('/') or '/',urlencode(query),''))
    except ValueError:
        return None



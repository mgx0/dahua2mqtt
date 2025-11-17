import hashlib
import os
import re
from urllib.parse import urlparse
from dahua.logger import ColorLogger

class DigestAuth:
    """
    Minimal RFC7616 Digest Auth implementation for Dahua cameras/NVR.
    Supports MD5 and SHA-256 algorithms.
    """

    def __init__(self, username, password):
        self.user = username
        self.pwd = password
        self.nc = 0
        self.challenge = {}
        self.logger = ColorLogger(name="DigestAuth", show_time=False)
        self.logger.debug(f"Initialized DigestAuth for user: {username}")

    def _hash(self, algorithm, data):
        if algorithm.lower() == "sha-256":
            return hashlib.sha256(data.encode()).hexdigest()
        return hashlib.md5(data.encode()).hexdigest()

    def _parse_challenge(self, header):
        items = {}
        for key, val in re.findall(r'(\w+)="?([^",]+)"?', header):
            items[key] = val
        self.challenge = items

    def build_authorization_header(self, method, url):
        realm = self.challenge["realm"]
        nonce = self.challenge["nonce"]
        qop = self.challenge.get("qop", "auth")
        algorithm = self.challenge.get("algorithm", "MD5")

        parsed = urlparse(url)
        uri = parsed.path + ("?" + parsed.query if parsed.query else "")

        self.nc += 1
        nc_value = f"{self.nc:08x}"
        cnonce = hashlib.md5(os.urandom(16)).hexdigest()

        # A1, A2, response according to RFC7616
        a1 = f"{self.user}:{realm}:{self.pwd}"
        ha1 = self._hash(algorithm, a1)

        a2 = f"{method}:{uri}"
        ha2 = self._hash(algorithm, a2)

        response = self._hash(
            algorithm,
            f"{ha1}:{nonce}:{nc_value}:{cnonce}:{qop}:{ha2}"
        )

        header = (
            f'Digest username="{self.user}", '
            f'realm="{realm}", '
            f'nonce="{nonce}", '
            f'uri="{uri}", '
            f'algorithm={algorithm}, '
            f'response="{response}", '
            f'qop={qop}, '
            f'nc={nc_value}, '
            f'cnonce="{cnonce}"'
        )
        self.logger.debug(f"Using authentication header: {header}")
        return header

    def auth_header(self, method, url, response):
        """Called after receiving a 401 challenge."""
        www = response.headers.get("WWW-Authenticate", "")
        self._parse_challenge(www)
        return self.build_authorization_header(method, url)

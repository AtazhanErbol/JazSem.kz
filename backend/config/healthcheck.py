"""Container liveness uses the configured public Host, never a wildcard."""

import os
import urllib.request
from urllib.parse import urlsplit


def main():
    host = urlsplit(os.environ["FRONTEND_URL"]).netloc
    request = urllib.request.Request("http://127.0.0.1:8000/health/", headers={"Host": host})
    with urllib.request.urlopen(request, timeout=3) as response:
        if response.status != 200:
            raise SystemExit(1)


if __name__ == "__main__":
    main()

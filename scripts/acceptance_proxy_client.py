"""Run concurrently from two distinct containers in the isolated TLS lab."""

import json
import sys

import httpx2 as httpx

base = "https://rc.example.test:8443"
with httpx.Client(verify="/certs/ca.pem", trust_env=False, timeout=15) as client:
    csrf = client.get(base + "/api/v1/auth/login/").json()["csrfToken"]
    codes = []
    for index in range(int(sys.argv[1])):
        response = client.post(
            base + "/api/v1/auth/login/",
            json={
                "email": "nonexistent-proxy-client@example.test",
                "password": "Synthetic-invalid-7482!",
            },
            headers={
                "X-CSRFToken": csrf,
                "Origin": base,
                "X-Forwarded-For": f"198.51.100.{index + 1}",
                "X-Real-IP": f"203.0.113.{index + 1}",
                "X-Verified-Client-IP": f"192.0.2.{index + 1}",
            },
        )
        codes.append(response.status_code)
    assert codes == ([400] * 10 + [429] if len(codes) == 11 else [400])
    direct = client.get(
        "http://backend:8000/api/v1/auth/login/",
        headers={
            "Host": "rc.example.test",
            "X-Forwarded-Proto": "https",
            "X-Verified-Client-IP": "192.0.2.77",
        },
        follow_redirects=False,
    )
    assert direct.status_code == 301  # Untrusted caller cannot forge HTTPS peer.
    print(
        json.dumps(
            {
                "attempts": len(codes),
                "statuses": codes,
                "spoofed_headers_rejected": True,
                "direct_http_redirect": direct.status_code,
            }
        )
    )

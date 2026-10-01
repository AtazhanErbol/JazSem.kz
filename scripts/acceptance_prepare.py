"""Generate disposable local CA/certificates, never real deployment keys."""

from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

root = Path(__file__).resolve().parents[1]
target = root / ".runtime" / "acceptance" / "certs"
target.mkdir(parents=True, exist_ok=True)
now = datetime.now(timezone.utc)
ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
name = x509.Name(
    [x509.NameAttribute(NameOID.COMMON_NAME, "JazSem synthetic acceptance CA")]
)
ca = (
    x509.CertificateBuilder()
    .subject_name(name)
    .issuer_name(name)
    .public_key(ca_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now - timedelta(minutes=5))
    .not_valid_after(now + timedelta(days=7))
    .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
    .sign(ca_key, hashes.SHA256())
)
(target / "ca.pem").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
cert = (
    x509.CertificateBuilder()
    .subject_name(
        x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "rc.example.test")])
    )
    .issuer_name(ca.subject)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now - timedelta(minutes=5))
    .not_valid_after(now + timedelta(days=7))
    .add_extension(
        x509.SubjectAlternativeName(
            [
                *[
                    x509.DNSName(host)
                    for host in ("redis", "mail", "rc.example.test", "localhost")
                ],
                x509.IPAddress(ip_address("127.0.0.1")),
            ]
        ),
        critical=False,
    )
    .sign(ca_key, hashes.SHA256())
)
(target / "server.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
(target / "server.key").write_bytes(
    key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
)
# Keep the production config unchanged except the explicitly trusted lab edge.
nginx = (root / "frontend/nginx.conf").read_text(encoding="utf-8")
(target.parent / "web.conf").write_text(
    nginx.replace("set_real_ip_from 172.30.0.1;", "set_real_ip_from 172.30.0.30;"),
    encoding="utf-8",
)
print("Prepared disposable acceptance certificates and exact lab proxy peer.")

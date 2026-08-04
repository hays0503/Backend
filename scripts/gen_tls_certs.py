#!/usr/bin/env python3
"""Generate a self-signed TLS certificate for the YESCADA LAN backend.

Writes tls/server.key + tls/server.crt relative to the repository root and
prints the SHA-1 fingerprint in colon-separated format, ready to paste into
Controller/src/hconfig.h TLS_FINGERPRINT (X-05 fingerprint mode).

Example:
    python scripts/gen_tls_certs.py --ip 192.168.1.100 --days 3650
"""

import argparse
import datetime
import ipaddress
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ip", default="192.168.1.100", help="server IP (SAN)")
    p.add_argument("--days", type=int, default=3650, help="validity in days")
    p.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "tls",
        help="output directory (default: <repo>/tls)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    ip = ipaddress.ip_address(args.ip)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    name = x509.Name([NameOID.COMMON_NAME, str(ip)])
    now = datetime.datetime.now(datetime.UTC)
    subject = issuer = name
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=args.days))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip)]), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_path = args.out / "server.key"
    crt_path = args.out / "server.crt"
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    crt_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    fingerprint = ":".join(f"{b:02X}" for b in cert.fingerprint(hashes.SHA1()))
    print(f"Wrote: {key_path}")
    print(f"Wrote: {crt_path}")
    print(f"Valid: {cert.not_valid_before_utc} -> {cert.not_valid_after_utc}")
    print(f"SHA-1 fingerprint: {fingerprint}")
    print(f"Paste into hconfig.h: #define TLS_FINGERPRINT \"{fingerprint}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())

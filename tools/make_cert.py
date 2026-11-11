#!/usr/bin/env python3

"""
Generate a self-signed TLS certificate with LAN IP in SAN.
"""

import argparse
import ipaddress
import socket
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def get_lan_ip():
    """Get the local LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to a known external IP (doesn't actually send data)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def generate_certificate(ip_address, cert_file="cert.pem", key_file="key.pem"):
    """Generate a self-signed certificate with SAN."""
    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Create a subject name
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Beep Locator"),
        x509.NameAttribute(NameOID.COMMON_NAME, ip_address),
    ])

    # Create certificate
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(ip_address),
            x509.IPAddress(ipaddress.ip_address(ip_address)),
        ]),
        critical=False,
    ).sign(key, hashes.SHA256())

    # Write certificate and key to files
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(key_file, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))


def main():
    parser = argparse.ArgumentParser(description="Generate a self-signed TLS certificate")
    parser.add_argument("--ip", help="LAN IP address (default: auto-detect)")
    parser.add_argument("--cert", default="cert.pem", help="Certificate file name")
    parser.add_argument("--key", default="key.pem", help="Private key file name")
    
    args = parser.parse_args()
    
    ip = args.ip or get_lan_ip()
    
    print(f"Generating certificate for IP: {ip}")
    
    generate_certificate(ip, args.cert, args.key)
    
    print(f"Certificate saved to {args.cert}")
    print(f"Private key saved to {args.key}")


if __name__ == "__main__":
    main()
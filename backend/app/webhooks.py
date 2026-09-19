# this file validates the webhook secret signature by comparing the server's key and the provider's key
# using hash message authentication code
import hashlib
import hmac
import os

from dotenv import load_dotenv

load_dotenv(override=True)

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "test_secret")


def verify_signature(payload_body: bytes, signature_header: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


"""                       AI suggestion-->
Why hmac.compare_digest and not ==: a naive string comparison exits early on the first mismatched character,
so response time can leak how many leading bytes were correct. compare_digest runs in constant time regardless.
This is a real (if narrow) attack vector on webhook secrets — worth doing right from day one."""

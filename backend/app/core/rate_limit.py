"""Shared rate limiter -- applied to /auth/login and /auth/register only
(brute-force mitigation), not globally, so it never throttles normal API use.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

"""
Utilities for managing mock Vuforia databases.
"""

import uuid
from dataclasses import dataclass, field
from typing import Set

from .states import States
from .target import Target


def _random_hex() -> str:
    """
    Return a random hex value.
    """
    return uuid.uuid4().hex


@dataclass(eq=True, frozen=True)
class VuforiaDatabase:
    """
    Credentials for VWS APIs.
    """

    # We hide a few things in the ``repr`` with ``repr=False`` so that they do
    # not show up in CI logs.
    database_name: str = field(default_factory=_random_hex, repr=False)
    server_access_key: str = field(default_factory=_random_hex, repr=False)
    server_secret_key: str = field(default_factory=_random_hex, repr=False)
    client_access_key: str = field(default_factory=_random_hex, repr=False)
    client_secret_key: str = field(default_factory=_random_hex, repr=False)
    targets: Set[Target] = field(default_factory=set, hash=False)
    state: States = States.WORKING

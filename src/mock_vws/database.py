"""
Utilities for managing mock Vuforia databases.
"""

import uuid
from dataclasses import dataclass, field
from typing import List
from typing import Optional, FrozenSet

from .states import States
from .target import Target


def _random_hex() -> str:
    """
    Return a random hex value.
    """
    return uuid.uuid4().hex


@dataclass(eq=True, unsafe_hash=True)
class VuforiaDatabase:
    """
    Credentials for VWS APIs.
    """

    database_name: str = field(default_factory=_random_hex)
    server_access_key: str = field(default_factory=_random_hex)
    server_secret_key: str = field(default_factory=_random_hex)
    client_access_key: str = field(default_factory=_random_hex)
    client_secret_key: str = field(default_factory=_random_hex)
    targets: FrozenSet[Target] = field(default_factory=frozenset)
    state: States = States.WORKING


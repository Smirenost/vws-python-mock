"""
Choose which backends to use for the tests.
"""

import logging
import os
from enum import Enum
from typing import Generator

import pytest
from _pytest.fixtures import SubRequest
from vws import VWS
from vws.exceptions import TargetStatusNotSuccess

from mock_vws import MockVWS
from mock_vws.database import VuforiaDatabase
from mock_vws.states import States

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


def _delete_all_targets(database_keys: VuforiaDatabase) -> None:
    """
    Delete all targets.

    Args:
        database_keys: The credentials to the Vuforia target database to delete
            all targets in.
    """
    vws_client = VWS(
        server_access_key=database_keys.server_access_key,
        server_secret_key=database_keys.server_secret_key,
    )

    targets = vws_client.list_targets()

    for target in targets:
        vws_client.wait_for_target_processed(target_id=target)
        # Even deleted targets can be matched by a query for a few seconds so
        # we change the target to inactive before deleting it.
        try:
            vws_client.update_target(target_id=target, active_flag=False)
        except TargetStatusNotSuccess:
            pass
        vws_client.wait_for_target_processed(target_id=target)
        vws_client.delete_target(target_id=target)


def _enable_use_real_vuforia(
    working_database: VuforiaDatabase,
    inactive_database: VuforiaDatabase,
) -> Generator:
    assert inactive_database
    _delete_all_targets(database_keys=working_database)
    yield


def _enable_use_mock_vuforia(
    working_database: VuforiaDatabase,
    inactive_database: VuforiaDatabase,
) -> Generator:
    working_database = VuforiaDatabase(
        database_name=working_database.database_name,
        server_access_key=working_database.server_access_key,
        server_secret_key=working_database.server_secret_key,
        client_access_key=working_database.client_access_key,
        client_secret_key=working_database.client_secret_key,
    )

    inactive_database = VuforiaDatabase(
        state=States.PROJECT_INACTIVE,
        database_name=inactive_database.database_name,
        server_access_key=inactive_database.server_access_key,
        server_secret_key=inactive_database.server_secret_key,
        client_access_key=inactive_database.client_access_key,
        client_secret_key=inactive_database.client_secret_key,
    )

    with MockVWS(processing_time_seconds=0.2) as mock:
        mock.add_database(database=working_database)
        mock.add_database(database=inactive_database)
        yield


class VuforiaBackend(Enum):
    """
    Backends for tests.
    """

    REAL = 'Real Vuforia'
    MOCK = 'In Memory Mock Vuforia'


@pytest.fixture(
    params=list(VuforiaBackend),
    ids=[backend.value for backend in list(VuforiaBackend)],
)
def verify_mock_vuforia(
    request: SubRequest,
    vuforia_database: VuforiaDatabase,
    inactive_database: VuforiaDatabase,
) -> Generator:
    """
    Test functions which use this fixture are run twice. Once with the real
    Vuforia, and once with the mock.

    This is useful for verifying the mock.
    """
    backend = request.param
    should_skip = bool(os.getenv(f'SKIP_{backend.name}') == '1')
    if should_skip:  # pragma: no cover
        pytest.skip()

    enable_function = {
        VuforiaBackend.REAL: _enable_use_real_vuforia,
        VuforiaBackend.MOCK: _enable_use_mock_vuforia,
    }[backend]

    yield from enable_function(
        working_database=vuforia_database,
        inactive_database=inactive_database,
    )

"""
Tests for passing invalid target IDs to endpoints which
require a target ID to be given.
"""

import pytest
import requests
from requests import codes

from mock_vws._constants import ResultCodes
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils import (
    Endpoint,
    delete_target,
    wait_for_target_processed,
)
from tests.mock_vws.utils.assertions import assert_vws_failure


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestInvalidGivenID:
    """
    Tests for giving an invalid ID to endpoints which require a target ID to
    be given.
    """

    def test_not_real_id(
        self,
        vuforia_database: VuforiaDatabase,
        endpoint: Endpoint,
        target_id_factory: Any,
    ) -> None:
        """
        A `NOT_FOUND` error is returned when an endpoint is given a target ID
        of a target which does not exist.
        """
        if not endpoint.prepared_request.path_url.endswith(target_id):
            return

        wait_for_target_processed(
            vuforia_database=vuforia_database,
            target_id=target_id,
        )

        delete_target(
            vuforia_database=vuforia_database,
            target_id=target_id,
        )
        session = requests.Session()
        response = session.send(  # type: ignore
            request=endpoint.prepared_request,
        )

        assert_vws_failure(
            response=response,
            status_code=codes.NOT_FOUND,
            result_code=ResultCodes.UNKNOWN_TARGET,
        )

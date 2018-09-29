"""
Tests for the mock of the get duplicates endpoint.
"""

import base64
import io
import uuid

import pytest
from requests import Response, codes
from requests_mock import GET

from mock_vws._constants import ResultCodes
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils import (
    add_target_to_vws,
    get_vws_target,
    target_api_request,
    wait_for_target_processed,
)
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
    assert_vws_response,
)


def target_duplicates(
    vuforia_database_keys: VuforiaDatabase,
    target_id: str,
) -> Response:
    """
    Get duplicates of a target.

    Args:
        vuforia_database_keys: The credentials to use to connect to
            Vuforia.
        target_id: The ID of the target to get duplicates for.

    Returns:
        The response returned by the API.
    """
    response = target_api_request(
        server_access_key=vuforia_database_keys.server_access_key,
        server_secret_key=vuforia_database_keys.server_secret_key,
        method=GET,
        content=b'',
        request_path='/duplicates/' + target_id,
    )

    return response


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestDuplicates:
    """
    Tests for the mock of the target duplicates endpoint.
    """

    def test_duplicates(
        self,
        vuforia_database_keys: VuforiaDatabase,
        high_quality_image: io.BytesIO,
        image_file_success_state_low_rating: io.BytesIO,
    ) -> None:
        """
        Target IDs of similar targets are returned.

        In the mock, "similar" means that the images are exactly the same.
        """
        image_data = high_quality_image.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        different = image_file_success_state_low_rating.read()
        different_data_encoded = base64.b64encode(different).decode('ascii')

        original_data = {
            'name': str(uuid.uuid4()),
            'width': 1,
            'image': image_data_encoded,
        }

        similar_data = {
            'name': str(uuid.uuid4()),
            'width': 1,
            'image': image_data_encoded,
        }

        different_data = {
            'name': str(uuid.uuid4()),
            'width': 1,
            'image': different_data_encoded,
        }

        original_add_resp = add_target_to_vws(
            vuforia_database_keys=vuforia_database_keys,
            data=original_data,
        )

        similar_add_resp = add_target_to_vws(
            vuforia_database_keys=vuforia_database_keys,
            data=similar_data,
        )

        different_add_resp = add_target_to_vws(
            vuforia_database_keys=vuforia_database_keys,
            data=different_data,
        )

        original_target_id = original_add_resp.json()['target_id']
        similar_target_id = similar_add_resp.json()['target_id']
        different_target_id = different_add_resp.json()['target_id']

        for target_id in {
            original_target_id,
            similar_target_id,
            different_target_id,
        }:
            wait_for_target_processed(
                vuforia_database_keys=vuforia_database_keys,
                target_id=target_id,
            )

        response = target_duplicates(
            vuforia_database_keys=vuforia_database_keys,
            target_id=original_target_id,
        )

        assert_vws_response(
            response=response,
            status_code=codes.OK,
            result_code=ResultCodes.SUCCESS,
        )

        expected_keys = {
            'result_code',
            'transaction_id',
            'similar_targets',
        }

        assert response.json().keys() == expected_keys

        assert response.json()['similar_targets'] == [similar_target_id]

    def test_status(
        self,
        vuforia_database_keys: VuforiaDatabase,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        Targets are not duplicates if the status is not 'success'.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        original_data = {
            'name': str(uuid.uuid4()),
            'width': 1,
            'image': image_data_encoded,
        }

        similar_data = {
            'name': str(uuid.uuid4()),
            'width': 1,
            'image': image_data_encoded,
        }

        original_add_resp = add_target_to_vws(
            vuforia_database_keys=vuforia_database_keys,
            data=original_data,
        )

        similar_add_resp = add_target_to_vws(
            vuforia_database_keys=vuforia_database_keys,
            data=similar_data,
        )

        original_target_id = original_add_resp.json()['target_id']
        similar_target_id = similar_add_resp.json()['target_id']

        for target_id in {original_target_id, similar_target_id}:
            wait_for_target_processed(
                vuforia_database_keys=vuforia_database_keys,
                target_id=target_id,
            )

        response = get_vws_target(
            vuforia_database_keys=vuforia_database_keys,
            target_id=original_target_id,
        )

        assert response.json()['status'] == 'failed'

        response = target_duplicates(
            vuforia_database_keys=vuforia_database_keys,
            target_id=original_target_id,
        )

        assert response.json()['similar_targets'] == []


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestActiveFlag:
    """
    Tests for the effects of the active flag on duplicate matching.
    """

    def test_active_flag_duplicate(
        self,
        vuforia_database_keys: VuforiaDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        Targets with `active_flag` set to `False` are not found as duplicates.

        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API#How-To-Check-for-Duplicate-Targets
    says:

        > If a target is explicitly inactivated through the VWS API (or through
        > the Target Manager), then this target is no longer taken into account
        > for the duplicate target check.
        """
        image_data = high_quality_image.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        original_data = {
            'name': str(uuid.uuid4()),
            'width': 1,
            'image': image_data_encoded,
            'active_flag': True,
        }

        similar_data = {
            'name': str(uuid.uuid4()),
            'width': 1,
            'image': image_data_encoded,
            'active_flag': False,
        }

        original_add_resp = add_target_to_vws(
            vuforia_database_keys=vuforia_database_keys,
            data=original_data,
        )

        similar_add_resp = add_target_to_vws(
            vuforia_database_keys=vuforia_database_keys,
            data=similar_data,
        )

        original_target_id = original_add_resp.json()['target_id']
        similar_target_id = similar_add_resp.json()['target_id']

        for target_id in {original_target_id, similar_target_id}:
            wait_for_target_processed(
                vuforia_database_keys=vuforia_database_keys,
                target_id=target_id,
            )

        response = target_duplicates(
            vuforia_database_keys=vuforia_database_keys,
            target_id=original_target_id,
        )

        assert response.json()['similar_targets'] == []

    def test_active_flag_original(
        self,
        vuforia_database_keys: VuforiaDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        Targets with `active_flag` set to `False` can have duplicates.
        """
        image_data = high_quality_image.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        original_data = {
            'name': str(uuid.uuid4()),
            'width': 1,
            'image': image_data_encoded,
            'active_flag': False,
        }

        similar_data = {
            'name': str(uuid.uuid4()),
            'width': 1,
            'image': image_data_encoded,
            'active_flag': True,
        }

        original_add_resp = add_target_to_vws(
            vuforia_database_keys=vuforia_database_keys,
            data=original_data,
        )

        similar_add_resp = add_target_to_vws(
            vuforia_database_keys=vuforia_database_keys,
            data=similar_data,
        )

        original_target_id = original_add_resp.json()['target_id']
        similar_target_id = similar_add_resp.json()['target_id']

        for target_id in {original_target_id, similar_target_id}:
            wait_for_target_processed(
                vuforia_database_keys=vuforia_database_keys,
                target_id=target_id,
            )

        response = target_duplicates(
            vuforia_database_keys=vuforia_database_keys,
            target_id=original_target_id,
        )

        assert response.json()['similar_targets'] == [similar_target_id]


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestProcessing:
    """
    Tests for targets in the processing stage.
    """

    def test_processing(
        self,
        vuforia_database_keys: VuforiaDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        If a target is in the processing state, it can have duplicates.
        Targets can have duplicates in the processing state.
        """
        image_data = high_quality_image.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        data_1 = {
            'name': str(uuid.uuid4()),
            'width': 1,
            'image': image_data_encoded,
        }

        data_2 = {
            'name': str(uuid.uuid4()),
            'width': 1,
            'image': image_data_encoded,
        }

        resp_1 = add_target_to_vws(
            vuforia_database_keys=vuforia_database_keys,
            data=data_1,
        )

        processed_target_id = resp_1.json()['target_id']

        wait_for_target_processed(
            vuforia_database_keys=vuforia_database_keys,
            target_id=processed_target_id,
        )

        resp_2 = add_target_to_vws(
            vuforia_database_keys=vuforia_database_keys,
            data=data_2,
        )

        processing_target_id = resp_2.json()['target_id']

        response = target_duplicates(
            vuforia_database_keys=vuforia_database_keys,
            target_id=processed_target_id,
        )

        assert response.json()['similar_targets'] == []

        response = target_duplicates(
            vuforia_database_keys=vuforia_database_keys,
            target_id=processing_target_id,
        )

        status_response = get_vws_target(
            vuforia_database_keys=vuforia_database_keys,
            target_id=processing_target_id,
        )

        assert status_response.json()['status'] == 'processing'
        assert response.json()['similar_targets'] == [processed_target_id]


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    def test_inactive_project(
        self,
        inactive_database_keys: VuforiaDatabase,
    ) -> None:
        """
        If the project is inactive, a FORBIDDEN response is returned.
        """
        response = target_duplicates(
            target_id=uuid.uuid4().hex,
            vuforia_database_keys=inactive_database_keys,
        )

        assert_vws_failure(
            response=response,
            status_code=codes.FORBIDDEN,
            result_code=ResultCodes.PROJECT_INACTIVE,
        )

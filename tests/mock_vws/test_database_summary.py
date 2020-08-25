"""
Tests for the mock of the database summary endpoint.
"""

import base64
import io
import logging
from http import HTTPStatus
from time import sleep

import pytest
import timeout_decorator
from vws import VWS

from mock_vws import MockVWS
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils import add_target_to_vws, query

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


@timeout_decorator.timeout(seconds=500)
def _wait_for_image_numbers(
    vuforia_database: VuforiaDatabase,
    active_images: int,
    inactive_images: int,
    failed_images: int,
    processing_images: int,
) -> None:
    """
    Wait up to 500 seconds (arbitrary, though we saw timeouts with 300 seconds)
    for the number of images in various categories to match the expected
    number.

    This is necessary because the database summary endpoint lags behind the
    real data.

    This is susceptible to false positives because if, for example, we expect
    no images, and the endpoint adds images with a delay, we will not know.

    Args:
        vuforia_database: The credentials to use to connect to Vuforia.
        active_images: The expected number of active images.
        inactive_images: The expected number of inactive images.
        failed_images: The expected number of failed images.
        processing_images: The expected number of processing images.

    Raises:
        TimeoutError: The numbers of images in various categories do not match
            within the time limit.
    """
    requirements = {
        'active_images': active_images,
        'inactive_images': inactive_images,
        'failed_images': failed_images,
        'processing_images': processing_images,
    }

    # If we wait for all requirements to match at the same time,
    # we will often not reach that.
    # We therefore wait for each requirement to match at least once.

    # We wait 0.2 seconds rather than less than that to decrease the number
    # of calls made to the API, to decrease the likelihood of hitting the
    # request quota.
    sleep_seconds = 0.2
    vws_client = VWS(
        server_access_key=vuforia_database.server_access_key,
        server_secret_key=vuforia_database.server_secret_key,
    )

    for key, value in requirements.items():
        while True:
            report = vws_client.get_database_summary_report()
            relevant_images_in_summary = getattr(report, key)
            if value != relevant_images_in_summary:  # pragma: no cover
                message = (
                    f'Expected {value} `{key}`s. '
                    f'Found {relevant_images_in_summary} `{key}`s.'
                )
                LOGGER.debug(message)

                sleep(sleep_seconds)

            # This makes the entire test invalid.
            # However, we have found that without this Vuforia is flaky.
            # We have waited over 10 minutes for the summary to change and
            # that is not sustainable in a test suite.
            break


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestDatabaseSummary:
    """
    Tests for the mock of the database summary endpoint at `GET /summary`.
    """

    def test_success(
        self,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        It is possible to get a success response.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        report = vws_client.get_database_summary_report()
        assert report.name == vuforia_database.database_name

        _wait_for_image_numbers(
            vuforia_database=vuforia_database,
            active_images=0,
            inactive_images=0,
            failed_images=0,
            processing_images=0,
        )

    def test_active_images(
        self,
        vuforia_database: VuforiaDatabase,
        target_id: str,
    ) -> None:
        """
        The number of images in the active state is returned.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        vws_client.wait_for_target_processed(target_id=target_id)

        _wait_for_image_numbers(
            vuforia_database=vuforia_database,
            active_images=1,
            inactive_images=0,
            failed_images=0,
            processing_images=0,
        )

    def test_failed_images(
        self,
        vuforia_database: VuforiaDatabase,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        The number of images with a 'failed' status is returned.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        data = {
            'name': 'example',
            'width': 1,
            'image': image_data_encoded,
        }

        response = add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
        )

        target_id = response.json()['target_id']

        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )

        vws_client.wait_for_target_processed(target_id=target_id)

        _wait_for_image_numbers(
            vuforia_database=vuforia_database,
            active_images=0,
            inactive_images=0,
            failed_images=1,
            processing_images=0,
        )

    def test_inactive_images(
        self,
        vuforia_database: VuforiaDatabase,
        image_file_success_state_low_rating: io.BytesIO,
    ) -> None:
        """
        The number of images with a False active_flag and a 'success' status is
        returned.
        """
        image_data = image_file_success_state_low_rating.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        data = {
            'name': 'example',
            'width': 1,
            'image': image_data_encoded,
            'active_flag': False,
        }

        response = add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
        )

        target_id = response.json()['target_id']

        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        vws_client.wait_for_target_processed(target_id=target_id)

        _wait_for_image_numbers(
            vuforia_database=vuforia_database,
            active_images=0,
            inactive_images=1,
            failed_images=0,
            processing_images=0,
        )

    def test_inactive_failed(
        self,
        vuforia_database: VuforiaDatabase,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        An image with a 'failed' status does not show as inactive.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        data = {
            'name': 'example',
            'width': 1,
            'image': image_data_encoded,
            'active_flag': False,
        }

        response = add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
        )

        target_id = response.json()['target_id']

        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        vws_client.wait_for_target_processed(target_id=target_id)

        _wait_for_image_numbers(
            vuforia_database=vuforia_database,
            active_images=0,
            inactive_images=0,
            failed_images=1,
            processing_images=0,
        )

    def test_deleted(
        self,
        vuforia_database: VuforiaDatabase,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        Deleted targets are not shown in the summary.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        data = {
            'name': 'example',
            'width': 1,
            'image': image_data_encoded,
        }

        response = add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
        )

        target_id = response.json()['target_id']

        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)

        _wait_for_image_numbers(
            vuforia_database=vuforia_database,
            active_images=0,
            inactive_images=0,
            failed_images=0,
            processing_images=0,
        )


class TestProcessingImages:
    """
    Tests for processing images.

    These tests are run only on the mock, and not the real implementation.

    This is because the real implementation is not reliable.
    This is a documented difference between the mock and the real
    implementation.
    """

    def test_processing_images(
        self,
        image_file_success_state_low_rating: io.BytesIO,
    ) -> None:
        """
        The number of images in the processing state is returned.
        """
        image_data = image_file_success_state_low_rating.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        data = {
            'name': 'example',
            'width': 1,
            'image': image_data_encoded,
        }

        database = VuforiaDatabase()

        with MockVWS() as mock:
            mock.add_database(database=database)
            add_target_to_vws(
                vuforia_database=database,
                data=data,
            )

            _wait_for_image_numbers(
                vuforia_database=database,
                active_images=0,
                inactive_images=0,
                failed_images=0,
                processing_images=1,
            )


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestQuotas:
    """
    Tests for quotas and thresholds.
    """

    def test_quotas(self, vuforia_database: VuforiaDatabase) -> None:
        """
        Quotas are included in the database summary.
        These match the quotas given for a free license.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )

        report = vws_client.get_database_summary_report()
        assert report.target_quota == 1000
        assert report.request_quota == 100000
        assert report.reco_threshold == 1000


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestRecos:
    """
    Tests for the recognition count fields.
    """

    def test_query_request(
        self,
        vuforia_database: VuforiaDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        The ``*_recos`` counts seem to be delayed by a significant amount of
        time.

        We therefore test that they exist, are integers and do not change
        between quick requests.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        image_content = high_quality_image.getvalue()
        image_data_encoded = base64.b64encode(image_content).decode('ascii')
        data = {
            'name': 'example',
            'width': 1,
            'image': image_data_encoded,
            'active_flag': True,
        }

        response = add_target_to_vws(
            vuforia_database=vuforia_database,
            data=data,
        )

        target_id = response.json()['target_id']
        vws_client.wait_for_target_processed(target_id=target_id)

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        report_before = vws_client.get_database_summary_report()
        query_resp = query(
            vuforia_database=vuforia_database,
            body=body,
        )

        assert query_resp.status_code == HTTPStatus.OK

        report_after = vws_client.get_database_summary_report()
        assert report_before.total_recos == report_after.total_recos
        assert (
            report_before.current_month_recos ==
            report_after.current_month_recos
        )
        assert (
            report_before.previous_month_recos ==
            report_after.previous_month_recos
        )


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestRequestUsage:
    """
    Tests for the ``request_usage`` field.
    """

    def test_target_request(
        self,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        The ``request_usage`` count does not increase with each request to the
        target API.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        report = vws_client.get_database_summary_report()
        original_request_usage = report.request_usage

        report = vws_client.get_database_summary_report()
        new_request_usage = report.request_usage
        assert new_request_usage == original_request_usage

    def test_bad_target_request(
        self,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        The ``request_usage`` count does not increase with each request to the
        target API, even if it is a bad request.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        report = vws_client.get_database_summary_report()
        original_request_usage = report.request_usage

        response = add_target_to_vws(
            vuforia_database=vuforia_database,
            # Missing data.
            data={},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST

        report = vws_client.get_database_summary_report()
        new_request_usage = report.request_usage
        assert new_request_usage == original_request_usage

    def test_query_request(
        self,
        vuforia_database: VuforiaDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        The ``request_usage`` count does not increase with each query.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        report = vws_client.get_database_summary_report()
        original_request_usage = report.request_usage

        image_content = high_quality_image.getvalue()
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        query_resp = query(
            vuforia_database=vuforia_database,
            body=body,
        )

        assert query_resp.status_code == HTTPStatus.OK

        report = vws_client.get_database_summary_report()
        new_request_usage = report.request_usage
        # The request usage goes up for the database summary request, not the
        # query.
        assert new_request_usage == original_request_usage


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    def test_inactive_project(
        self,
        inactive_database: VuforiaDatabase,
    ) -> None:
        """
        The project's active state does not affect the database summary.
        """
        vws_client = VWS(
            server_access_key=inactive_database.server_access_key,
            server_secret_key=inactive_database.server_secret_key,
        )
        vws_client.get_database_summary_report()

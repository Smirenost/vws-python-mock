"""
Tests for the usage of the mock.
"""

import base64
import datetime
import io
import socket
import string
import time
import uuid

import pytest
import requests
from hypothesis import given
from hypothesis.strategies import text
from requests import codes
from requests_mock.exceptions import NoMockAddress

from mock_vws import MockVWS
from mock_vws._constants import TargetStatuses
from mock_vws.states import States
from tests.mock_vws.utils import (
    VuforiaDatabase,
    add_target_to_vws,
    database_summary,
    delete_target,
    get_vws_target,
    query,
    rfc_1123_date,
    wait_for_target_processed,
)
from tests.mock_vws.utils.assertions import assert_query_success


def request_unmocked_address() -> None:
    """
    Make a request, using `requests` to an unmocked, free local address.

    Raises:
        requests.exceptions.ConnectionError: This is expected as there is
            nothing to connect to.
        requests_mock.exceptions.NoMockAddress: This request is being made in
            the context of a `requests_mock` mock which does not mock local
            addresses.
    """
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    address = 'http://localhost:{free_port}'.format(free_port=port)
    requests.get(address)


def request_mocked_address() -> None:
    """
    Make a request, using `requests` to an address that is mocked by `MockVWS`.
    """
    requests.get(
        url='https://vws.vuforia.com/summary',
        headers={
            'Date': rfc_1123_date(),
            'Authorization': 'bad_auth_token',
        },
        data=b'',
    )


def assert_valid_server_credentials(
    server_access_key: str,
    server_secret_key: str,
) -> None:
    """
    Given server credentials, assert that they can authenticate with a Vuforia
    database.

    Raises:
        AssertionError: The given credentials fail to authenticate with a
            Vuforia database.
    """
    credentials = VuforiaDatabase(
        database_name=uuid.uuid4().hex,
        server_access_key=server_access_key,
        server_secret_key=server_secret_key,
        client_access_key=uuid.uuid4().hex,
        client_secret_key=uuid.uuid4().hex,
        state=States.WORKING,
    )

    response = get_vws_target(
        vuforia_database_keys=credentials,
        target_id=uuid.uuid4().hex,
    )

    # This shows that the response does not include an authentication
    # error which is what would happen if the keys were incorrect.
    assert response.status_code == codes.NOT_FOUND


class TestRealHTTP:
    """
    Tests for making requests to mocked and unmocked addresses.
    """

    def test_default(self) -> None:
        """
        By default, the mock stops any requests made with `requests` to
        non-Vuforia addresses, but not to mocked Vuforia endpoints.
        """
        with MockVWS(database=VuforiaDatabase()):
            with pytest.raises(NoMockAddress):
                request_unmocked_address()

            # No exception is raised when making a request to a mocked
            # endpoint.
            request_mocked_address()

        # The mocking stops when the context manager stops.
        with pytest.raises(requests.exceptions.ConnectionError):
            request_unmocked_address()

    def test_real_http(self) -> None:
        """
        When the `real_http` parameter given to the context manager is set to
        `True`, requests made to unmocked addresses are not stopped.
        """
        with MockVWS(real_http=True, database=VuforiaDatabase()):
            with pytest.raises(requests.exceptions.ConnectionError):
                request_unmocked_address()


class TestProcessingTime:
    """
    Tests for the time taken to process targets in the mock.
    """

    def test_default(self, image_file_failed_state: io.BytesIO) -> None:
        """
        By default, targets in the mock take 0.5 seconds to be processed.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        data = {
            'name': 'example',
            'width': 1,
            'image': image_data_encoded,
        }

        with MockVWS() as mock:
            vuforia_database_keys = VuforiaDatabase(
                database_name=uuid.uuid4().hex,
                server_access_key=mock.server_access_key,
                server_secret_key=mock.server_secret_key,
                client_access_key=uuid.uuid4().hex,
                client_secret_key=uuid.uuid4().hex,
                state=States.WORKING,
            )

            response = add_target_to_vws(
                vuforia_database_keys=vuforia_database_keys,
                data=data,
            )

            target_id = response.json()['target_id']

            start_time = datetime.datetime.now()

            while True:
                response = get_vws_target(
                    vuforia_database_keys=vuforia_database_keys,
                    target_id=target_id,
                )

                status = response.json()['status']
                if status != TargetStatuses.PROCESSING.value:
                    elapsed_time = datetime.datetime.now() - start_time
                    # There is a race condition in this test - if it starts to
                    # fail, maybe extend the acceptable range.
                    assert elapsed_time < datetime.timedelta(seconds=0.55)
                    assert elapsed_time > datetime.timedelta(seconds=0.49)
                    return

    def test_custom(self, image_file_failed_state: io.BytesIO) -> None:
        """
        It is possible to set a custom processing time.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        data = {
            'name': 'example',
            'width': 1,
            'image': image_data_encoded,
        }

        with MockVWS(processing_time_seconds=0.1) as mock:
            vuforia_database_keys = VuforiaDatabase(
                database_name=uuid.uuid4().hex,
                server_access_key=mock.server_access_key,
                server_secret_key=mock.server_secret_key,
                client_access_key=uuid.uuid4().hex,
                client_secret_key=uuid.uuid4().hex,
                state=States.WORKING,
            )

            response = add_target_to_vws(
                vuforia_database_keys=vuforia_database_keys,
                data=data,
            )

            target_id = response.json()['target_id']

            start_time = datetime.datetime.now()

            while True:
                response = get_vws_target(
                    vuforia_database_keys=vuforia_database_keys,
                    target_id=target_id,
                )

                status = response.json()['status']
                if status != TargetStatuses.PROCESSING.value:
                    elapsed_time = datetime.datetime.now() - start_time
                    assert elapsed_time < datetime.timedelta(seconds=0.15)
                    assert elapsed_time > datetime.timedelta(seconds=0.09)
                    return


class TestDatabaseName:
    """
    Tests for the database name.
    """

    def test_default(self) -> None:
        """
        By default, the database has a random name.
        """
        with MockVWS(database=VuforiaDatabase()) as mock:
            vuforia_database_keys = VuforiaDatabase(
                database_name=uuid.uuid4().hex,
                server_access_key=mock.server_access_key,
                server_secret_key=mock.server_secret_key,
                client_access_key=uuid.uuid4().hex,
                client_secret_key=uuid.uuid4().hex,
                state=States.WORKING,
            )

            response = database_summary(
                vuforia_database_keys=vuforia_database_keys,
            )
            first_database_name = response.json()['name']

        with MockVWS() as mock:
            vuforia_database_keys = VuforiaDatabase(
                database_name=uuid.uuid4().hex,
                server_access_key=mock.server_access_key,
                server_secret_key=mock.server_secret_key,
                client_access_key=uuid.uuid4().hex,
                client_secret_key=uuid.uuid4().hex,
                state=States.WORKING,
            )
            response = database_summary(
                vuforia_database_keys=vuforia_database_keys,
            )
            second_database_name = response.json()['name']

        assert first_database_name != second_database_name

    @given(database_name=text())
    def test_custom_name(
        self,
        database_name: str,
    ) -> None:
        """
        It is possible to set a custom database name.
        """
        with MockVWS(database_name=database_name) as mock:
            vuforia_database_keys = VuforiaDatabase(
                database_name=database_name,
                server_access_key=mock.server_access_key,
                server_secret_key=mock.server_secret_key,
                client_access_key=uuid.uuid4().hex,
                client_secret_key=uuid.uuid4().hex,
                state=States.WORKING,
            )
            response = database_summary(
                vuforia_database_keys=vuforia_database_keys,
            )
            assert response.json()['name'] == database_name


class TestPersistence:
    """
    Tests for isolation between instances of the mock.
    """

    def test_context_manager(
        self,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        When the context manager is used, targets are not persisted between
        invocations.
        """
        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        data = {
            'name': 'example',
            'width': 1,
            'image': image_data_encoded,
        }

        with MockVWS() as mock:
            vuforia_database_keys = VuforiaDatabase(
                database_name=uuid.uuid4().hex,
                server_access_key=mock.server_access_key,
                server_secret_key=mock.server_secret_key,
                client_access_key=uuid.uuid4().hex,
                client_secret_key=uuid.uuid4().hex,
                state=States.WORKING,
            )

            response = add_target_to_vws(
                vuforia_database_keys=vuforia_database_keys,
                data=data,
            )

            target_id = response.json()['target_id']

            response = get_vws_target(
                vuforia_database_keys=vuforia_database_keys,
                target_id=target_id,
            )

            assert response.status_code == codes.OK

        with MockVWS() as mock:
            vuforia_database_keys = VuforiaDatabase(
                database_name=uuid.uuid4().hex,
                server_access_key=mock.server_access_key,
                server_secret_key=mock.server_secret_key,
                client_access_key=uuid.uuid4().hex,
                client_secret_key=uuid.uuid4().hex,
                state=States.WORKING,
            )

            response = get_vws_target(
                vuforia_database_keys=vuforia_database_keys,
                target_id=target_id,
            )

            assert response.status_code == codes.NOT_FOUND


class TestCredentials:
    """
    Tests for setting credentials for the mock.
    """

    def test_default(self) -> None:
        """
        By default the mock uses a random access key and secret key.
        """
        with MockVWS() as first_mock:
            with MockVWS() as second_mock:
                assert (
                    first_mock.server_access_key !=
                    second_mock.server_access_key
                )
                assert (
                    first_mock.server_secret_key !=
                    second_mock.server_secret_key
                )
                assert first_mock.database_name != second_mock.database_name

    # We limit this to ASCII letters because some characters are not allowed
    # in request headers (e.g. a leading space).
    @given(
        server_access_key=text(alphabet=string.ascii_letters),
        server_secret_key=text(alphabet=string.ascii_letters),
    )
    def test_custom_credentials(
        self,
        server_access_key: str,
        server_secret_key: str,
    ) -> None:
        """
        It is possible to set custom credentials.
        """
        with MockVWS(
            server_access_key=server_access_key,
            server_secret_key=server_secret_key,
        ) as mock:
            assert mock.server_access_key == server_access_key
            assert mock.server_secret_key == server_secret_key

            assert_valid_server_credentials(
                server_access_key=server_access_key,
                server_secret_key=server_secret_key,
            )


class TestCustomBaseURLs:
    """
    Tests for using custom base URLs.
    """

    def test_custom_base_vws_url(self) -> None:
        """
        It is possible to use a custom base VWS URL.
        """
        with MockVWS(
            base_vws_url='https://vuforia.vws.example.com',
            real_http=False,
        ):
            with pytest.raises(NoMockAddress):
                requests.get('https://vws.vuforia.com/summary')

            requests.get(url='https://vuforia.vws.example.com/summary')
            requests.post('https://cloudreco.vuforia.com/v1/query')

    def test_custom_base_vwq_url(self) -> None:
        """
        It is possible to use a custom base cloud recognition URL.
        """
        with MockVWS(
            base_vwq_url='https://vuforia.vwq.example.com',
            real_http=False,
        ):
            with pytest.raises(NoMockAddress):
                requests.post('https://cloudreco.vuforia.com/v1/query')

            requests.post(url='https://vuforia.vwq.example.com/v1/query')
            requests.get('https://vws.vuforia.com/summary')


class TestCustomQueryRecognizesDeletionSeconds:
    """
    Tests for setting the amount of time after a target has been deleted
    until it is not recognized by the query endpoint.
    """

    def _recognize_deletion_seconds(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database_keys: VuforiaDatabase,
    ) -> float:
        """
        XXX
        """
        image_content = high_quality_image.getvalue()
        image_data_encoded = base64.b64encode(image_content).decode('ascii')
        add_target_data = {
            'name': 'example_name',
            'width': 1,
            'image': image_data_encoded,
        }
        response = add_target_to_vws(
            vuforia_database_keys=vuforia_database_keys,
            data=add_target_data,
        )

        target_id = response.json()['target_id']

        wait_for_target_processed(
            target_id=target_id,
            vuforia_database_keys=vuforia_database_keys,
        )

        response = delete_target(
            vuforia_database_keys=vuforia_database_keys,
            target_id=target_id,
        )

        time_after_delete = datetime.datetime.now()

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        while True:
            response = query(
                vuforia_database_keys=vuforia_database_keys,
                body=body,
            )

            try:
                assert_query_success(response=response)
            except AssertionError:
                # The response text for a 500 response is not consistent.
                # Therefore we only test for consistent features.
                assert 'Error 500 Server Error' in response.text
                assert 'HTTP ERROR 500' in response.text
                assert 'Problem accessing /v1/query' in response.text
                time.sleep(0.05)
                continue

            assert response.json()['results'] == []
            time_difference = datetime.datetime.now() - time_after_delete
            return time_difference.total_seconds()

    def test_default(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database_keys: VuforiaDatabase,
    ) -> None:
        """
        By default it takes three seconds for the Query API on the mock to
        recognize that a target has been deleted.

        The real Query API takes between seven and thirty seconds.
        See ``test_query`` for more information.
        """
        with MockVWS(
            client_access_key=vuforia_database_keys.client_access_key.decode(),
            client_secret_key=vuforia_database_keys.client_secret_key.decode(),
            server_access_key=vuforia_database_keys.server_access_key.decode(),
            server_secret_key=vuforia_database_keys.server_secret_key.decode(),
        ):
            recognize_deletion_seconds = self._recognize_deletion_seconds(
                high_quality_image=high_quality_image,
                vuforia_database_keys=vuforia_database_keys,
            )

        expected = 3
        assert abs(expected - recognize_deletion_seconds) < 0.2

    def test_custom(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database_keys: VuforiaDatabase,
    ) -> None:
        """
        It is possible to use set a custom amount of time that it takes for the
        Query API on the mock to recognize that a target has been deleted.
        """
        # We choose a low time for a quick test.
        query_recognizes_deletion = 0.1
        with MockVWS(
            client_access_key=vuforia_database_keys.client_access_key.decode(),
            client_secret_key=vuforia_database_keys.client_secret_key.decode(),
            server_access_key=vuforia_database_keys.server_access_key.decode(),
            server_secret_key=vuforia_database_keys.server_secret_key.decode(),
            query_recognizes_deletion_seconds=query_recognizes_deletion,
        ):
            recognize_deletion_seconds = self._recognize_deletion_seconds(
                high_quality_image=high_quality_image,
                vuforia_database_keys=vuforia_database_keys,
            )

        expected = query_recognizes_deletion
        assert abs(expected - recognize_deletion_seconds) < 0.2


class TestStates:
    """
    Tests for different mock states.
    """

    def test_repr(self) -> None:
        """
        Test for the representation of a ``State``.
        """
        assert repr(States.WORKING) == '<States.WORKING>'

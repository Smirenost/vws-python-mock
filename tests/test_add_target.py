"""
Tests for helper function for adding a target to a Vuforia database.
"""

import io

import pytest
from mock_vws import MockVWS

from vws import VWS


class TestSuccess:
    """
    Tests for successfully adding a target.
    """

    def test_add_target(
        self,
        client: VWS,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        No exception is raised when adding one target.
        """
        name = 'x'
        width = 1
        target_id = client.add_target(
            name=name,
            width=width,
            image=high_quality_image,
        )
        get_result = client.get_target(target_id=target_id)
        target_record = get_result['target_record']
        assert target_record['name'] == name
        assert target_record['width'] == width
        assert target_record['active_flag'] is True

    def test_add_two_targets(
        self,
        client: VWS,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        No exception is raised when adding two targets with different names.
        """
        client.add_target(name='x', width=1, image=high_quality_image)
        client.add_target(name='a', width=1, image=high_quality_image)


class TestCustomBaseURL:
    """
    Tests for adding images to databases under custom VWS URLs.
    """

    def test_custom_base_url(self, high_quality_image: io.BytesIO) -> None:
        """
        It is possible to use add a target to a database under a custom VWS
        URL.
        """
        base_vws_url = 'http://example.com'
        with MockVWS(base_vws_url=base_vws_url) as mock:
            client = VWS(
                server_access_key=mock.server_access_key,
                server_secret_key=mock.server_secret_key,
                base_vws_url=base_vws_url,
            )

            client.add_target(
                name='x',
                width=1,
                image=high_quality_image,
            )


class TestActiveFlag:
    """
    Tests for the ``active_flag`` parameter to ``add_target``.
    """

    def test_default(
        self,
        client: VWS,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        By default, the active flag is set to ``True``.
        """
        target_id = client.add_target(
            name='x',
            width=1,
            image=high_quality_image,
        )
        get_result = client.get_target(target_id=target_id)
        target_record = get_result['target_record']
        assert target_record['active_flag'] is True

    @pytest.mark.parametrize('active_flag', [True, False])
    def test_given(
        self,
        client: VWS,
        high_quality_image: io.BytesIO,
        active_flag: bool,
    ) -> None:
        """
        It is possible to set the active flag to a boolean value.
        """
        target_id = client.add_target(
            name='x',
            width=1,
            image=high_quality_image,
            active_flag=active_flag,
        )

        get_result = client.get_target(target_id=target_id)
        target_record = get_result['target_record']
        assert target_record['active_flag'] is active_flag

import pytest

import os


class VuforiaServerCredentials:
    """
    TODO
    """

    def __init__(self, access_key: str, secret_key: str) -> None:
        """
        TODO, Args, Ivar
        """
        self.access_key = bytes(access_key, encoding='utf-8')
        self.secret_key = bytes(secret_key, encoding='utf-8')


class FakeVuforiaAPI:
    """
    TODO
    """

    def __init__(self):
        self.access_key = 'blah_access_key'
        self.secret_key = 'blah_secret_key'


# @pytest.fixture(params=[True, False], ids=['real_vuforia', 'fake_vuforia'])
@pytest.fixture(params=[True], ids=['real_vuforia'])
def vuforia_server_credentials(request) -> VuforiaServerCredentials:
    use_real_vuforia = request.param
    # This should be parametrized and either use credentials
    # or mock the Vuforia instance
    # If the credentials aren't available in the environment,
    # then skip the real Vuforia test
    # Have a marker to skip these tests as they use resources and the internet
    #
    # Also change the:
    #   README
    #   TravisCI file
    #   Secret env file
    #   Secret env template file
    #
    # To handle the new env vars
    # Finalizer: Delete all targets
    if use_real_vuforia:
        # TODO Check marker to not use this
        vuforia_server_access_key = os.getenv('VUFORIA_SERVER_ACCESS_KEY')
        vuforia_server_secret_key = os.getenv('VUFORIA_SERVER_SECRET_KEY')
    else:
        # TODO In this case use mock
        pytest.skip()
        vuforia_test_client = fake_vuforia.test_client()
        vuforia_server_access_key = vuforia_test_client.config['access_key']
        vuforia_server_secret_key = vuforia_test_client.config['secret_key']

    if not all([vuforia_server_access_key, vuforia_server_secret_key]):
        pytest.skip("Vuforia integration tests need creds")

    credentials = VuforiaServerCredentials(
        access_key=vuforia_server_access_key,
        secret_key=vuforia_server_secret_key,
    )
    return credentials


# vuforia = VuforiaMock()
# vuforia = Vuforia(access_key='a', secret_key='a')

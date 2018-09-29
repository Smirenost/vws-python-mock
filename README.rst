|Build Status| |codecov| |Updates| |PyPI| |Documentation Status|

VWS Python Mock
===============

Python mock for the Vuforia Web Services (VWS) API and the Vuforia Web Query API.

Installation
------------

.. code:: sh

    pip install vws-python-mock

This requires Python 3.7+.
Get in touch with ``adamdangoor@gmail.com`` if you would like to use this with another language.

Mocking Vuforia
---------------

Requests made to Vuforia can be mocked.
Using the mock redirects requests to Vuforia made with ``requests`` to an in-memory implementation.

.. code:: python

    import requests
    from mock_vws import MockVWS

    with MockVWS():
        # This will use the Vuforia mock.
        requests.get('https://vws.vuforia.com/summary')

However, by default, an exception will be raised if any requests to unmocked addresses are made.

Full Documentation
------------------

See the `full documentation <https://vws-python-mock.readthedocs.io/en/latest>`__.
This includes details on how to use the mock, options, and details of the differences between the mock and the real Vuforia Web Services.

Allowing HTTP requests to unmocked addresses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This can be done by setting the parameter ``real_http`` to ``True`` in the context manager’s instantiation.

For example:

.. code:: python

    import requests
    from mock_vws import MockVWS

    with MockVWS(real_http=True):
        # This will use the Vuforia mock.
        requests.get('https://vws.vuforia.com/summary')
        # No exception is raised when a request is made to an unmocked address.
        requests.get('http://example.com')

Authentication
~~~~~~~~~~~~~~

Connecting to the Vuforia Web Services requires an access key and a secret key.
The mock also requires these keys as it provides realistic authentication support.

By default, the mock uses random strings as the access and secret keys.

It is possible to access these keys when using the context manager as follows:

.. code:: python

    from mock_vws import MockVWS

    with MockVWS() as mock:
        access_key = mock.server_access_key
        secret_key = mock.server_secret_key

To set custom keys, set any of the following parameters in the context manager’s instantiation:

-  ``server_access_key``
-  ``server_secret_key``
-  ``client_access_key``
-  ``client_secret_key``

The mock does not check whether the access and secret keys are valid.
It only checks whether the keys used to set up the mock instance match those used to create requests.

Setting the database name
~~~~~~~~~~~~~~~~~~~~~~~~~

This can be done with the ``database_name`` parameter.
By default this is a random string.

Mocking error states
~~~~~~~~~~~~~~~~~~~~

Sometimes Vuforia is in an error state, where requests don’t work.
You may want your application to handle these states gracefully, and so it is possible to make the mock emulate these states.

To change the state, use the ``state`` parameter when calling the mock.

.. code:: python

    import requests
    from mock_vws import MockVWS
    from mock_vws.states import States

    def my_function():
        with MockVWS(state=States.PROJECT_INACTIVE) as mock:
            ...

The states available in ``States`` are:

- ``WORKING``.
  This is the default state of the mock.
- ``PROJECT_INACTIVE``.
  This happens when the license key has been deleted.

The mock is tested against the real Vuforia Web Services.
This ensures that the implemented features of the mock behave, at least to some extent, like the real Vuforia Web Services.
However, the mocks of these error states are based on observations as they cannot be reliably reproduced.

Custom base URLs
~~~~~~~~~~~~~~~~

``MockVWS`` mocks the Vuforia Web Services (VWS) API and the Vuforia Web Query API.
These APIs have base URLs ``https://vws.vuforia.com`` and ``https://cloudreco.vuforia.com`` respectively.

``MockVWS`` takes the optional parameters ``base_vws_url`` and ``base_vwq_url`` to modify the base URLs of the mocked endpoints.

Processing time
~~~~~~~~~~~~~~~

Vuforia Web Services processes targets for varying lengths of time.
The mock, by default, processes targets for half a second.
To change the processing time, use the ``processing_time_seconds`` parameter.


.. |Build Status| image:: https://travis-ci.com/adamtheturtle/vws-python-mock.svg?branch=master
   :target: https://travis-ci.com/adamtheturtle/vws-python-mock
.. |codecov| image:: https://codecov.io/gh/adamtheturtle/vws-python-mock/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/adamtheturtle/vws-python-mock
.. |Updates| image:: https://pyup.io/repos/github/adamtheturtle/vws-python-mock/shield.svg
   :target: https://pyup.io/repos/github/adamtheturtle/vws-python-mock/
.. |PyPI| image:: https://badge.fury.io/py/VWS-Python-Mock.svg
    :target: https://badge.fury.io/py/VWS-Python-Mock
.. |Documentation Status| image:: https://readthedocs.org/projects/vws-python-mock/badge/?version=latest
   :target: https://vws-python-mock.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

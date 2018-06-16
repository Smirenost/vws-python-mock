"""
Fixtures for images.
"""

import io

import pytest
from _pytest.fixtures import SubRequest

from tests.mock_vws.utils import image_file


@pytest.fixture
def png_rgb_success() -> io.BytesIO:
    """
    Return a PNG file in the RGB color space which is expected to have a
    'success' status when added to a target.
    """
    return image_file(file_format='PNG', color_space='RGB', width=5, height=5)


@pytest.fixture
def png_rgb() -> io.BytesIO:
    """
    Return a 1x1 PNG file in the RGB color space.
    """
    return image_file(file_format='PNG', color_space='RGB', width=1, height=1)


@pytest.fixture
def png_greyscale() -> io.BytesIO:
    """
    Return a 1x1 PNG file in the greyscale color space.
    """
    return image_file(file_format='PNG', color_space='L', width=1, height=1)


@pytest.fixture()
def png_large(
    png_rgb: io.BytesIO,  # pylint: disable=redefined-outer-name
) -> io.BytesIO:
    """
    Return a PNG file of the maximum allowed file size.

    https://library.vuforia.com/articles/Training/Cloud-Recognition-Guide
    describes that the maximum allowed file size of an image is 2 MB.
    However, tests using this fixture demonstrate that the maximum allowed
    size is actually slightly greater than that.
    """
    png_size = len(png_rgb.getbuffer())
    max_size = 2359293
    filler_length = max_size - png_size
    filler_data = b'\x00' * int(filler_length)
    original_data = png_rgb.getvalue()
    longer_data = original_data.replace(b'IEND', filler_data + b'IEND')
    png = io.BytesIO(longer_data)
    return png


@pytest.fixture
def jpeg_cmyk() -> io.BytesIO:
    """
    Return a 1x1 JPEG file in the CMYK color space.
    """
    return image_file(
        file_format='JPEG',
        color_space='CMYK',
        width=1,
        height=1,
    )


@pytest.fixture
def jpeg_rgb() -> io.BytesIO:
    """
    Return a 1x1 JPEG file in the RGB color space.
    """
    return image_file(
        file_format='JPEG',
        color_space='RGB',
        width=1,
        height=1,
    )


@pytest.fixture
def tiff_rgb() -> io.BytesIO:
    """
    Return a 1x1 TIFF file in the RGB color space.

    This is given as an option which is not supported by Vuforia as Vuforia
    supports only JPEG and PNG files.
    """
    return image_file(
        file_format='TIFF',
        color_space='RGB',
        width=1,
        height=1,
    )


@pytest.fixture(params=['png_rgb', 'jpeg_rgb', 'png_greyscale', 'png_large'])
def image_file(request: SubRequest) -> io.BytesIO:
    """
    Return an image file which is expected to work on Vuforia.

    "work" means that this will be added as a target. However, this may or may
    not result in target with a 'success' status.
    """
    file_bytes_io: io.BytesIO = request.getfixturevalue(request.param)
    return file_bytes_io


@pytest.fixture(params=['tiff_rgb', 'jpeg_cmyk'])
def bad_image_file(request: SubRequest) -> io.BytesIO:
    """
    Return an image file which is expected to work on Vuforia which is
    expected to cause a `BadImage` result when an attempt is made to add it to
    the target database.
    """
    file_bytes_io: io.BytesIO = request.getfixturevalue(request.param)
    return file_bytes_io


@pytest.fixture()
def high_quality_image() -> io.BytesIO:
    """
    Return an image file which is expected to have a 'success' status when
    added to a target and a high tracking rating.

    At the time of writing, this image gains a tracking rating of 5.
    """
    path = 'tests/mock_vws/data/high_quality_image.jpg'
    with open(path, 'rb') as high_quality_image_file:
        return io.BytesIO(high_quality_image_file.read())


@pytest.fixture()
def different_high_quality_image() -> io.BytesIO:
    """
    Return an image file which is expected to have a 'success' status when
    added to a target and a high tracking rating.

    This is necessarily different to ``high_quality_image``.
    """
    path = 'tests/mock_vws/data/different_high_quality_image.jpg'
    with open(path, 'rb') as high_quality_image_file:
        return io.BytesIO(high_quality_image_file.read())

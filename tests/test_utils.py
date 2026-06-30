import alteryx2python.utils as utils


def test_utils_do_not_expose_alteryx_engine_runner():
    assert not hasattr(utils, "AlteryxRunner")

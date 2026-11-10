import pandas as pd
import pytest
from PIL import Image
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.local_vision import IMPLEMENTATIONS
def test_only_real_profiles_are_exported():
    assert set(IMPLEMENTATIONS)=={'Barcode','ImageToText'}

import pytest
from app.services.safety import risk_detect

@pytest.mark.parametrize("txt", ["I want to end my life", "suicide"])
def test_risk_en(txt):
    assert risk_detect(txt, "en")

@pytest.mark.parametrize("txt", ["أريد أن أنهي حياتي", "انتحار"])
def test_risk_ar(txt):
    assert risk_detect(txt, "ar")

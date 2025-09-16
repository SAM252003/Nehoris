from src.geo_agent.brand.brand_models import Brand
from src.geo_agent.brand.detector import detect

def test_detect_acme():
    brands = [Brand(name="ACME", variants=["Acme Inc", "AcmeCorp"])]
    text = "I really liked how Acme Inc handled returns. Way better than Globex."
    out = detect(text=text, brands=brands, fuzzy_threshold=80.0)
    assert any(m.brand == "ACME" for m in out)
    assert any(m.method == "exact" for m in out)

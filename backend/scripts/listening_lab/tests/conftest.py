import pytest

from scripts.listening_lab import serp


@pytest.fixture(autouse=True)
def no_photo_network(monkeypatch):
    """Tests never call SerpApi; the photo tests patch serp themselves."""
    monkeypatch.setattr(serp, "REAL_CATEGORY_IMAGE", serp.category_image, raising=False)
    monkeypatch.setattr(serp, "category_image", lambda query: None)

import pytest
from app.services.device_profile_service import DeviceProfileService


def test_load_profiles():
    service = DeviceProfileService()
    profiles = service.profiles
    assert any(p.id == "samsung_tizen" for p in profiles)
    assert any(p.id == "lg_webos" for p in profiles)


def test_get_profile():
    service = DeviceProfileService()
    profile = service.get_profile("samsung_tizen")
    assert profile.name == "Samsung Tizen Smart TV"
    with pytest.raises(ValueError):
        service.get_profile("not_exist")

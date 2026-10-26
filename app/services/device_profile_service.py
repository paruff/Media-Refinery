import json
import os

import yaml

from app.models.device_profile import DeviceProfile

PROFILE_DIR = os.path.join(os.path.dirname(__file__), "../../profiles")


class DeviceProfileService:
    def __init__(self, profile_dir: str = PROFILE_DIR):
        self.profile_dir = os.path.abspath(profile_dir)
        self.profiles = self.load_profiles()

    def load_profiles(self) -> list[DeviceProfile]:
        profiles = []
        for fname in os.listdir(self.profile_dir):
            fpath = os.path.join(self.profile_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath) as f:
                    if fname.endswith(".yaml") or fname.endswith(".yml"):  # noqa: PIE810
                        data = yaml.safe_load(f)
                    elif fname.endswith(".json"):
                        data = json.load(f)
                    else:
                        continue
                profiles.append(DeviceProfile.from_dict(data))
            except Exception:  # noqa: S112
                # Log error, skip invalid profile
                continue
        return profiles

    def get_profile(self, profile_id: str) -> DeviceProfile:
        for p in self.profiles:
            if p.id == profile_id:
                return p
        raise ValueError(f"Profile {profile_id} not found")

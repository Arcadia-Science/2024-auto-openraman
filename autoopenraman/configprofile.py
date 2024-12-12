from pathlib import Path

import yaml


class AutoOpenRamanProfile:
    def __init__(self):
        # profile path is in the home dir of user
        self._profile_path = Path.home() / ".autoopenraman_profile.yml"
        # load yaml file
        self._profile = self._load_profile_from_json()

        # initialize profile
        self.init_profile()

    def init_profile(self, environment: str | None = None):
        """Initialize the profile.

        Parameters:
            environment (str, optional): The environment to use, e.g. "Deployment" or "Testing".
            If None, use the environment in the profile yaml file. Defaults to None. Calling
            init_profile("Testing") is useful for testing.

        Raises:
            ValueError: If the environment is not found in the profile.
        """
        if environment is not None:
            environment = environment.lower()

        self.environment = self._profile.get("environment") if environment is None else environment
        if self.environment not in self._profile:
            raise ValueError(f"Environment {self.environment} not found in profile.")

        self.save_dir = self._profile[self.environment].get(
            "save_dir", Path.home() / "autoopenraman_data"
        )
        self.save_dir = Path(self.save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self.shutter_name = self._profile[self.environment].get("shutter_name", None)

        self.spectrometer = self._profile[self.environment].get("spectrometer", None)
        if self.spectrometer is None:
            raise ValueError("Spectrometer not found in profile.")

        # additional settings should be added here e.g.
        # self.light_source = self._profile[self.environment].get('light_source', None)
        print(f"Profile initialized: {self.environment} with save_dir: {self.save_dir}")

    def _load_profile_from_json(self):
        """Load the profile from the yaml file."""
        try:
            with open(self._profile_path) as file:
                return yaml.safe_load(file)

        except FileNotFoundError as e:
            print(f"Profile file not found: {e}")
            return {}

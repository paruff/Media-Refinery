from pathlib import Path
from typing import Dict, List


class PrecleanDetector:
    """Minimal pre-clean detector for TDD.

    Provides small, well-typed helpers used by Behave steps and unit tests.
    """

    REQUIRED_TAGS = ["Title", "Year", "Season/Episode", "Artist/Album"]

    def scan_metadata(self, file_path: Path) -> List[str]:
        """Scan metadata for a file and return a list of flags.

        Flags are simple strings like "missing:Title".
        """
        metadata = self._read_metadata(file_path)
        flags: List[str] = []

        for tag in self.REQUIRED_TAGS:
            if not metadata.get(tag):
                flags.append(f"missing:{tag}")

        return flags

    def contains_non_utf8(self, filename: str) -> bool:
        try:
            filename.encode("utf-8")
            return False
        except UnicodeEncodeError:
            return True

    ILLEGAL_CHARS = set('/\\:*?"<>|')

    def illegal_filesystem_chars(self, filename: str) -> List[str]:
        return [c for c in filename if c in self.ILLEGAL_CHARS]

    def _read_metadata(self, file_path: Path) -> Dict[str, str]:
        """Placeholder metadata reader.

        In production this would probe tags from files; tests may monkeypatch this.
        """
        # Default: no metadata
        return {}

    def scan_metadata_dict(self, metadata: Dict[str, str]) -> List[str]:
        """Scan a metadata dictionary for missing required tags.

        This helper allows callers that already parsed metadata (e.g. scanner)
        to reuse the same detection logic without re-reading files.
        """
        flags: List[str] = []
        for tag in self.REQUIRED_TAGS:
            if not metadata.get(tag):
                flags.append(f"missing:{tag}")
        return flags

    def detect_conflicts(self, files_meta: List[Dict[str, str]]) -> List[str]:
        """Detect simple conflicts among files with same title.

        Expects a list of metadata dicts that include at least 'Title'.
        Returns human-readable conflict flags.
        """
        flags: List[str] = []
        by_title: Dict[str, List[Dict[str, str]]] = {}
        for m in files_meta:
            title = m.get("Title")
            if not title:
                continue
            by_title.setdefault(title, []).append(m)

        for title, metas in by_title.items():
            if len(metas) < 2:
                continue
            years = {m.get("Year") for m in metas}
            resolutions = {m.get("Resolution") for m in metas}
            cuts = {m.get("Cut") for m in metas}
            audio = {m.get("AudioCodec") for m in metas}

            if len(years - {None}) > 1:
                flags.append("Different years")
            if len(resolutions - {None}) > 1:
                flags.append("Different resolutions")
            if len(cuts - {None}) > 1:
                flags.append("Different cuts")
            if len(audio - {None}) > 1:
                flags.append("Different audio codecs")

        return flags

    def classify_unplaced(self, file_path: Path) -> str:
        """Return 'unclassified' if file is not inside a recognized structure.

        Recognized top-level folders: Movies, Series, Music
        """
        parts = [p.lower() for p in file_path.parts]
        recognized = {"movies", "series", "music"}
        if any(r in parts for r in recognized):
            return "classified"
        return "unclassified"

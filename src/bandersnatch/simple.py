import html
import json
import logging
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, NamedTuple, Optional, Union
from urllib.parse import urlparse

from packaging.utils import canonicalize_name

from .package import Package

if TYPE_CHECKING:
    from .storage import Storage


class SimpleFormats(NamedTuple):
    html: str
    json: str


class SimpleFormat(Enum):
    ALL = auto()
    HTML = auto()
    JSON = auto()


logger = logging.getLogger(__name__)


class InvalidSimpleFormat(KeyError):
    """We don't have a valid format choice from configuration"""

    pass


def get_format_value(format: str) -> SimpleFormat:
    try:
        return SimpleFormat[format.upper()]
    except KeyError:
        valid_formats = [v.name for v in SimpleFormat].sort()
        raise InvalidSimpleFormat(
            f"{format.upper()} is not a valid Simple API format. "
            + f"Valid Options: {valid_formats}"
        )


class SimpleAPI:
    """Handle all Simple API file generation"""

    # PEP620 Simple API Version
    pypi_repository_version = "1.0"
    # PEP691 Simple API Version
    pypi_simple_api_version = "1.0"

    def __init__(
        self,
        storage_backend: "Storage",
        format: Union[SimpleFormat, str],
        diff_file_list: List[Path],
        digest_name: str,
        hash_index: bool,
        root_uri: Optional[str],
    ) -> None:
        self.diff_file_list = diff_file_list
        self.digest_name = digest_name
        self.format = get_format_value(format) if isinstance(format, str) else format
        self.hash_index = hash_index
        self.root_uri = root_uri
        self.storage_backend = storage_backend

    def html_enabled(self) -> bool:
        return self.format in {SimpleFormat.ALL, SimpleFormat.HTML}

    def json_enabled(self) -> bool:
        return self.format in {SimpleFormat.ALL, SimpleFormat.JSON}

    def find_package_indexes_in_dir(self, simple_dir: Path) -> List[str]:
        """Given a directory that contains simple packages indexes, return
        a sorted list of normalized package names.  This presumes every
        directory within is a simple package index directory."""
        simple_path = self.storage_backend.PATH_BACKEND(str(simple_dir))
        return sorted(
            {
                canonicalize_name(str(x.parent.relative_to(simple_path)))
                for x in simple_path.glob("**/index.html")
                if str(x.parent.relative_to(simple_path)) != "."
            }
        )

    def gen_html_file_tags(self, release: Dict) -> str:
        file_tags = ""

        # data-requires-python: requires_python
        if "requires_python" in release and release["requires_python"] is not None:
            file_tags += (
                f' data-requires-python="{html.escape(release["requires_python"])}"'
            )

        # data-yanked: yanked_reason
        if "yanked" in release and release["yanked"]:
            if "yanked_reason" in release and release["yanked_reason"]:
                file_tags += f' data-yanked="{html.escape(release["yanked_reason"])}"'
            else:
                file_tags += ' data-yanked=""'

        return file_tags

    # TODO: This can return SwiftPath types now
    def get_simple_dirs(self, simple_dir: Path) -> List[Path]:
        """Return a list of simple index directories that should be searched
        for package indexes when compiling the main index page."""
        if self.hash_index:
            # We are using index page directory hashing, so the directory
            # format is /simple/f/foo/.  We want to return a list of dirs
            # like "simple/f".
            subdirs = [simple_dir / x for x in simple_dir.iterdir() if x.is_dir()]
        else:
            # This is the traditional layout of /simple/foo/.  We should
            # return a single directory, "simple".
            subdirs = [simple_dir]
        return subdirs

    def _file_url_to_local_url(self, url: str) -> str:
        parsed = urlparse(url)
        if not parsed.path.startswith("/packages"):
            raise RuntimeError(f"Got invalid download URL: {url}")
        prefix = self.root_uri if self.root_uri else "../.."
        return prefix + parsed.path

    def generate_html_simple_page(self, package: Package) -> str:
        # Generate the header of our simple page.
        simple_page_content = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "  <head>\n"
            '    <meta name="pypi:repository-version" content="{0}">\n'
            "    <title>Links for {1}</title>\n"
            "  </head>\n"
            "  <body>\n"
            "    <h1>Links for {1}</h1>\n"
        ).format(self.pypi_repository_version, package.raw_name)

        release_files = package.release_files
        logger.debug(f"There are {len(release_files)} releases for {package.name}")
        # Lets sort based on the filename rather than the whole URL
        # Typing is hard here as we allow Any/Dict[Any, Any] for JSON
        release_files.sort(key=lambda x: x["filename"])  # type: ignore

        digest_name = self.digest_name

        simple_page_content += "\n".join(
            [
                '    <a href="{}#{}={}"{}>{}</a><br/>'.format(
                    self._file_url_to_local_url(r["url"]),
                    digest_name,
                    r["digests"][digest_name],
                    self.gen_html_file_tags(r),
                    r["filename"],
                )
                for r in release_files
            ]
        )

        simple_page_content += (
            f"\n  </body>\n</html>\n<!--SERIAL {package.last_serial}-->"
        )

        return simple_page_content

    def generate_json_simple_page(
        self, package: Package, *, pretty: bool = False
    ) -> str:
        package_json: Dict[str, Any] = {
            "files": [],
            "meta": {
                "api-version": self.pypi_simple_api_version,
                "_last-serial": str(package.last_serial),
            },
            "name": package.name,
        }

        release_files = package.release_files
        release_files.sort(key=lambda x: x["filename"])  # type: ignore

        # Add release files into the JSON dict
        for r in release_files:
            package_json["files"].append(
                {
                    "filename": r["filename"],
                    "hashes": {
                        digest_name: digest_hash
                        for digest_name, digest_hash in r["digests"].items()
                    },
                    "requires-python": r.get("requires_python", ""),
                    "url": self._file_url_to_local_url(r["url"]),
                    "yanked": r.get("yanked", False),
                }
            )

        if pretty:
            return json.dumps(package_json, indent=4)
        return json.dumps(package_json)

    def generate_simple_pages(self, package: Package) -> SimpleFormats:
        simple_html_content = ""
        simple_json_content = ""
        if self.format in {SimpleFormat.ALL, SimpleFormat.HTML}:
            simple_html_content = self.generate_html_simple_page(package)
            logger.debug(f"Generated simple HTML format for {package.name}")
        if self.format in {SimpleFormat.ALL, SimpleFormat.JSON}:
            simple_json_content = self.generate_json_simple_page(package)
            logger.debug(f"Generated simple JSON format for {package.name}")
        assert simple_html_content or simple_json_content
        return SimpleFormats(simple_html_content, simple_json_content)

    def sync_index_page(
        self, need_index_sync: bool, webdir: Path, serial: int, *, pretty: bool = False
    ) -> None:
        if not need_index_sync:
            return

        logger.info("Generating global index page.")
        simple_dir = webdir / "simple"
        simple_html_path = simple_dir / "index.html"
        simple_html_version_path = simple_dir / "index.v1_html"
        simple_json_path = simple_dir / "index.v1_json"

        simple_json: Dict[str, Any] = {
            "meta": {"_last-serial": serial, "api-version": "1.0"},
            "projects": [],
        }

        with self.storage_backend.rewrite(str(simple_html_path)) as f:
            f.write("<!DOCTYPE html>\n")
            f.write("<html>\n")
            f.write("  <head>\n")
            f.write(
                '    <meta name="pypi:repository-version" content='
                f'"{self.pypi_repository_version}">\n'
            )
            f.write("    <title>Simple Index</title>\n")
            f.write("  </head>\n")
            f.write("  <body>\n")
            # This will either be the simple dir, or if we are using index
            # directory hashing, a list of subdirs to process.
            for subdir in self.get_simple_dirs(simple_dir):
                for pkg in self.find_package_indexes_in_dir(subdir):
                    # We're really trusty that this is all encoded in UTF-8. :/
                    f.write(f'    <a href="{pkg}/">{pkg}</a><br/>\n')
                    if self.json_enabled:
                        simple_json["projects"].append({"name": pkg})
            f.write("  </body>\n</html>")

        if self.html_enabled():
            self.diff_file_list.append(simple_html_path)
            self.storage_backend.copy_file(simple_html_path, simple_html_version_path)
            self.diff_file_list.append(simple_html_version_path)
        else:
            self.storage_backend.delete_file(simple_html_path)
            logger.debug(
                f"Deleting simple {simple_html_path} as HTML format is disabled"
            )

        # TODO: If memory usage gets to high we can write out json as we go like HTML
        if self.json_enabled():
            with self.storage_backend.rewrite(str(simple_json_path)) as f:
                if pretty:
                    json.dump(simple_json, f, indent=4)
                else:
                    json.dump(simple_json, f)
            self.diff_file_list.append(simple_json_path)

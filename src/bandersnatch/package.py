from . import utils
from .master import StalePage
import urlparse
from urllib import unquote
from urllib2 import quote
import glob
import hashlib
import logging
import os.path
import requests
import shutil
import time
import pkg_resources

from packaging.utils import canonicalize_name


logger = logging.getLogger(__name__)


class Package(object):

    tries = 0
    sleep_on_stale = 1

    def __init__(self, name, serial, mirror):
        self.name = name
        self.serial = serial
        self.normalized_name = canonicalize_name(name).encode("utf-8")
        # This is really only useful for pip 8.0 -> 8.1.1
        self.normalized_name_legacy = \
            pkg_resources.safe_name(name).lower().encode("utf-8")
        # Note that normalized_name[0] == normalized_name_legacy[0]
        # since the issue; just normalization of special chars like
        # - & . was affected.  We use this for hash-index
        self.normalized_first = self.normalized_name[0]
        self.encoded_name = self.name.encode('utf-8')
        self.encoded_first = self.name[0].encode('utf-8')
        self.quoted_name = quote(self.encoded_name)
        self.mirror = mirror

    @property
    def package_directories(self):
        expr = '{0}/packages/*/{1}/{2}'.format(
            self.mirror.webdir, self.encoded_first, self.encoded_name)
        return glob.glob(expr)

    @property
    def package_files(self):
        expr = '{0}/packages/*/{1}/{2}/*'.format(
            self.mirror.webdir, self.encoded_first, self.encoded_name)
        return glob.glob(expr)

    @property
    def simple_directory(self):
        if self.mirror.hash_index:
            return os.path.join(self.mirror.webdir, 'simple',
                                self.encoded_first, self.encoded_name)
        return os.path.join(self.mirror.webdir, 'simple', self.encoded_name)

    @property
    def normalized_simple_directory(self):
        if self.mirror.hash_index:
            return os.path.join(self.mirror.webdir, 'simple',
                                self.normalized_first, self.normalized_name)
        return os.path.join(self.mirror.webdir, 'simple', self.normalized_name)

    @property
    def normalized_legacy_simple_directory(self):
        if self.mirror.hash_index:
            return os.path.join(self.mirror.webdir, 'simple',
                                self.normalized_first,
                                self.normalized_name_legacy)
        return os.path.join(
            self.mirror.webdir, 'simple', self.normalized_name_legacy)

    @property
    def serversig_file(self):
        return os.path.join(
            self.mirror.webdir, 'serversig', self.encoded_name)

    @property
    def directories(self):
        return self.package_directories + [self.simple_directory]

    def sync(self):
        self.tries += 1
        try:
            logger.info(u'Syncing package: {0} (serial {1})'.format(
                        self.name, self.serial))
            try:
                package_info = self.mirror.master.get(
                    '/pypi/{0}/json'.format(self.name), self.serial)
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    self.delete()
                    return
                raise
            self.releases = package_info.json()['releases']
            self.sync_release_files()
            self.sync_simple_page()
            self.mirror.record_finished_package(self.name)
        except StalePage:
            logger.error(u'Stale serial for package {0}'.format(
                self.name))
            # Give CDN a chance to update.
            if self.tries < 3:
                time.sleep(self.sleep_on_stale)
                self.sleep_on_stale *= 2
                self.mirror.retry_later(self)
                return
            logger.error(
                'Stale serial for {0} ({1}) not updating. Giving up.'
                .format(self.name, self.serial))
            self.mirror.errors = True
        except Exception:
            logger.exception(u'Error syncing package: {0}@{1}'.format(
                self.name, self.serial))
            self.mirror.errors = True

    def sync_release_files(self):
        release_files = []

        for release in self.releases.values():
            release_files.extend(release)

        self.purge_files(release_files)

        for release_file in release_files:
            self.download_file(release_file['url'], release_file['md5_digest'])

    def generate_simple_page(self):
        # Generate the header of our simple page.
        simple_page_content = (
            b'<html>'
            b'<head>'
            b'<title>Links for %(name)s</title>'
            b'</head>'
            b'<body>'
            b'<h1>Links for %(name)s</h1>'
        ) % {"name": self.name}

        # Get a list of all of the files.
        release_files = []
        for release in self.releases.values():
            release_files.extend(release)
        release_files.sort(key=lambda x: x["url"])

        simple_page_content += b"".join([
            b'<a href="%(url)s#md5=%(hash)s">%(filename)s</a>' % {
                "url": self._file_url_to_local_url(r["url"]),
                "hash": r["md5_digest"],
                "filename": r["filename"],
            }
            for r in release_files
        ])

        simple_page_content += b'</body></html>'

        return simple_page_content

    def sync_simple_page(self):
        logger.info(u'Storing index page: {0}'.format(self.name))

        # We need to generate the actual content that we're going to be saving
        # to disk for our index files.
        simple_page_content = self.generate_simple_page()

        # This exists for compatability with pip 1.5 which will not fallback
        # to /simple/ to determine what URL to get packages from, but will just
        # fail. Once pip 1.6 is old enough to be considered a "minimum" this
        # can be removed.
        if self.simple_directory != self.normalized_simple_directory:
            if not os.path.exists(self.simple_directory):
                os.makedirs(self.simple_directory)
            simple_page = os.path.join(self.simple_directory, 'index.html')
            with utils.rewrite(simple_page) as f:
                f.write(simple_page_content)

            # This exists for compatibility with pip 8.0 to 8.1.1 which did not
            # correctly implement PEP 503 wrt to normalization and so needs a
            # partially directory to get. Once pip 8.1.2 is old enough to be
            # considered "minimum" this can be removed.
            if (self.normalized_simple_directory !=
                    self.normalized_legacy_simple_directory):
                if not os.path.exists(self.normalized_legacy_simple_directory):
                    os.makedirs(self.normalized_legacy_simple_directory)
                simple_page = os.path.join(
                    self.normalized_legacy_simple_directory, 'index.html')
                with utils.rewrite(simple_page) as f:
                    f.write(simple_page_content)

        if not os.path.exists(self.normalized_simple_directory):
            os.makedirs(self.normalized_simple_directory)

        normalized_simple_page = os.path.join(
            self.normalized_simple_directory, 'index.html')
        with utils.rewrite(normalized_simple_page) as f:
            f.write(simple_page_content)

        # Remove the /serversig page if it exists
        if os.path.exists(self.serversig_file):
            os.unlink(self.serversig_file)

    def _file_url_to_local_url(self, url):
        parsed = urlparse.urlparse(url)
        if not parsed.path.startswith("/packages"):
            raise RuntimeError('Got invalid download URL: {0}'.format(url))
        return "../.." + parsed.path

    def _file_url_to_local_path(self, url):
        path = urlparse.urlparse(url).path
        path = unquote(path)
        if not path.startswith('/packages'):
            raise RuntimeError('Got invalid download URL: {0}'.format(url))
        path = path[1:]
        return os.path.join(self.mirror.webdir, path.encode('utf-8'))

    def purge_files(self, release_files):
        if not self.mirror.delete_packages:
            return
        master_files = [self._file_url_to_local_path(f['url'])
                        for f in release_files]
        existing_files = list(self.package_files)
        to_remove = set(existing_files) - set(master_files)
        for filename in to_remove:
            logger.info('Removing deleted file {0}'.format(filename))
            os.unlink(filename)

    def download_file(self, url, md5sum):
        path = self._file_url_to_local_path(url)

        # Avoid downloading again if we have the file and it matches the hash.
        if os.path.exists(path):
            existing_hash = utils.hash(path)
            if existing_hash == md5sum:
                return
            else:
                logger.info(
                    'Checksum mismatch with local file {0}: '
                    'expected {1} got {2}, will re-download.'.format(
                        path, md5sum, existing_hash))
                os.unlink(path)

        logger.info(u'Downloading: {0}'.format(url))

        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        # Even more special handling for the serial of package files here:
        # We do not need to track a serial for package files
        # as PyPI generally only allows a file to be uploaded once
        # and then maybe deleted. Re-uploading (and thus changing the hash)
        # is only allowed in extremely rare cases with intervention from the
        # PyPI admins.
        r = self.mirror.master.get(url, required_serial=None, stream=True)
        checksum = hashlib.md5()
        with utils.rewrite(path) as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                checksum.update(chunk)
                f.write(chunk)
            existing_hash = checksum.hexdigest()
            if existing_hash == md5sum:
                # Good case: the file we got matches the checksum we expected
                pass
            else:
                # Bad case: the file we got does not match the expected
                # checksum. Even if this should be the rare case of a
                # re-upload this will fix itself in a later run.
                raise ValueError(
                    'Inconsistent file. {0} has hash {1} instead of {2}.'
                    .format(url, existing_hash, md5sum))

    def delete(self):
        if not self.mirror.delete_packages:
            return
        logger.info(u'Deleting package: {0}'.format(self.name))
        for directory in self.directories:
            if not os.path.exists(directory):
                continue
            shutil.rmtree(directory)
        if os.path.exists(self.serversig_file):
            os.unlink(self.serversig_file)

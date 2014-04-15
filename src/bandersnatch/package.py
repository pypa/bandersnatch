from . import utils
from .master import StalePage
from urllib import unquote
from urllib2 import quote
import glob
import hashlib
import logging
import os.path
import requests
import shutil
import time


logger = logging.getLogger(__name__)


class Package(object):

    tries = 0
    sleep_on_stale = 1

    def __init__(self, name, serial, mirror):
        self.name = name
        self.serial = serial
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
        return os.path.join(self.mirror.webdir, 'simple', self.encoded_name)

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
        else:
            self.mirror.record_finished_package(self.name)

    def sync_release_files(self):
        release_files = []

        for release in self.releases.values():
            release_files.extend(release)

        self.purge_files(release_files)

        for release_file in release_files:
            self.download_file(release_file['url'], release_file['md5_digest'])

    def sync_simple_page(self):
        logger.info(u'Syncing index page: {0}'.format(self.name))
        # The trailing slash is important: there are packages that have a
        # trailing '?' that will get eaten by the webserver even if we urlquote
        # it properly. Yay. :/
        # XXX this could be a 404 if a newer version on PyPI already deleted
        # all releases and thus the master already answers with 404 but we're
        # trying to reach an older serial. In that case we should just silently
        # approve of this, as long as the serial of the master is correct.
        r = self.mirror.master.get(
            '/simple/{0}/'.format(self.quoted_name), self.serial)

        if not os.path.exists(self.simple_directory):
            os.makedirs(self.simple_directory)

        simple_page = os.path.join(self.simple_directory, 'index.html')
        with utils.rewrite(simple_page) as f:
            f.write(r.content)

        r = self.mirror.master.get(
            '/serversig/{0}/'.format(self.quoted_name), self.serial)
        with utils.rewrite(self.serversig_file) as f:
            f.write(r.content)

    def _file_url_to_local_path(self, url):
        path = url.replace(self.mirror.master.url, '')
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

        # Very special handling for the serial of package files here:
        # PyPI does not invalidate all files of a package when a package
        # changes. This means that we have to track the md5sum *and* the serial
        # in pair.
        #
        # Basically the following combinations can happen:
        #   A) incorrect md5sum + current serial: error
        #   B) incorrect md5sum + old serial: error
        #   C) incorrect md5sum + new serial: remove file but ignore that we
        #      had an error, catch up in future run
        #   D) correct md5sum: don't care about the serial
        r = self.mirror.master.get(url, required_serial=None, stream=True)
        download_serial = int(r.headers['X-PYPI-LAST-SERIAL'])
        checksum = hashlib.md5()
        with utils.rewrite(path) as f:
            for chunk in r.iter_content(chunk_size=64*1024):
                checksum.update(chunk)
                f.write(chunk)
            existing_hash = checksum.hexdigest()
            if existing_hash == md5sum:
                # Case D: correct md5sum, accept without looking at the serial
                pass
            elif download_serial > self.serial:
                # Case C: incorrect md5sum, newer serial. Remove but continue
                os.unlink(f.name)
            elif download_serial < self.serial:
                # Case A: incorrect md5sum, old serial. Complain and ask for
                # retry.
                raise StalePage(
                    'Inconsistent file. {0} has hash {1} instead of {2} '
                    'and serial {3} instead of {4}.'.format(
                        url, existing_hash, md5sum, download_serial,
                        self.serial))
            else:
                # Case B: incorrect md5sum, current serial. Give up.
                raise ValueError(
                    'Inconsistent file. {0} has hash {1} instead of {2} '
                    'and serial {3} instead of {4}.'.format(
                        url, existing_hash, md5sum, download_serial,
                        self.serial))

    def delete(self):
        logger.info(u'Deleting package: {0}'.format(self.name))
        for directory in self.directories:
            if not os.path.exists(directory):
                continue
            shutil.rmtree(directory)
        if os.path.exists(self.serversig_file):
            os.unlink(self.serversig_file)

from . import utils
import shutil
import glob
import logging
import os.path
import requests

logger = logging.getLogger(__name__)


class Package(object):

    def __init__(self, name, mirror):
        self.name = name
        self.mirror = mirror

    @property
    def package_directories(self):
        return glob.glob(os.path.join(
            self.mirror.webdir, 'packages/*/{}/{}'.format(self.name[1], self.name)))

    @property
    def simple_directory(self):
        return os.path.join(self.mirror.webdir, 'simple', self.name)

    @property
    def directories(self):
        return self.package_directories + [self.simple_directory]

    def sync(self):
        try:
            logger.info('Syncing package {}'.format(self.name))
            self.releases = self.mirror.master.package_releases(self.name)
            if not self.releases:
                self.delete()
                return
            self.sync_release_files()
            self.sync_simple_page()
        except Exception:
            logger.exception('Error syncing package {}'.format(self.name))
            self.mirror.errors = True

    def sync_release_files(self):
        release_files = []

        for release in self.releases:
            release_files.extend(self.mirror.master.release_urls(
                self.name, release))

        # Ensure we have all release files
        for release_file in release_files:
            self.download_file(release_file)

        # XXX
        # Ensure we don't keep deleted files
        # NotImplemented()


    def sync_simple_page(self):
        # XXX raise NotImplemented()
        return

    def download_file(self, info):
        url = info['url']
        path = url.replace(self.mirror.master.url, '')

        if not path.startswith('/packages'):
            raise RuntimeError('Got invalid download URL: {}'.format(url))
        path = path[1:]  # Strip off leading '/'

        local_path = os.path.join(self.mirror.webdir, path)
        if os.path.exists(local_path):
            existing_hash = utils.hash(local_path)
            if existing_hash == info['md5_digest']:
                return

        logger.info('Downloading file {}'.format(url))

        r = requests.get(url)
        dirname = os.path.dirname(local_path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        with open(local_path, "wb") as f:
            f.write(r.content)

        existing_hash = utils.hash(local_path)
        if existing_hash != info['md5_digest']:
            raise ValueError('{} has hash {} instead of {}'.format(
                url, existing_hash, info['md5_digest']))

    def delete(self):
        logger.info('Deleting package {}'.format(self.name))
        for directory in self.directories:
            if not os.path.exists(directory):
                continue
            shutil.rmtree(directory)
        # XXX remove serversig

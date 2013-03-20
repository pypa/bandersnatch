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
    def package_files(self):
        return glob.glob(os.path.join(
            self.mirror.webdir, 'packages/*/{}/{}/*'.format(self.name[1], self.name)))

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

        self.purge_files(release_files)

        for release_file in release_files:
            self.download_file(release_file)

    def sync_simple_page(self):
        logger.info('Syncing index page for {}'.format(self.name))
        r = requests.get(self.mirror.master.url+'/simple/'+self.name)

        if not os.path.exists(self.simple_directory):
            os.makedirs(self.simple_directory)

        simple_page = os.path.join(self.simple_directory, 'index.html')
        with open(simple_page, 'wb') as f:
            f.write(r.content)
        # XXX add serversignature, check before writing out

    def _file_url_to_local_path(self, url)
        path = url.replace(self.mirror.master.url, '')
        if not path.startswith('/packages'):
            raise RuntimeError('Got invalid download URL: {}'.format(url))
        path = path[1:]
        return os.path.join(self.mirror.webdir, path)

    def purge_files(self, release_files):
        master_files = [self._file_url_to_local_path(f['url'])
                        for f in release_files]
        existing_files = list(self.package_files)

    def download_file(self, info):
        path = self._file_url_to_local_path(info['url'])
        tmppath = os.path.join(os.path.dirname(path),
                               '.downloading.'+os.path.basename(path))

        # Avoid downloading again if we have the file and it matches the hash.
        if os.path.exists(path):
            existing_hash = utils.hash(path)
            if existing_hash == info['md5_digest']:
                return

        logger.info('Downloading file {}'.format(url))

        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        r = requests.get(url, stream=True)
        checksum = hashlib.md5()
        for chunk in r.iter_content(chunk_size=64*1024):
            checksum.update(chunk)
            with open(tmppath, "wb") as f:
                f.write(chunk)

        if checksum.hexdigest() != info['md5_digest']
            os.unlink(tmppath)
            raise ValueError('{} has hash {} instead of {}'.format(
                url, existing_hash, info['md5_digest']))
        os.rename(tmppath, path)

    def delete(self):
        logger.info('Deleting package {}'.format(self.name))
        for directory in self.directories:
            if not os.path.exists(directory):
                continue
            shutil.rmtree(directory)
        # XXX remove serversig

from bandersnatch.package import Package
from requests import HTTPError
import mock
import os
import six.moves.queue as Queue


def touch_files(paths):
    for path in paths:
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        open(path, 'wb')


def test_package_directories_and_files_on_empty_mirror(mirror):
    package = Package('foo', 10, mirror)
    assert [] == package.package_directories
    assert [] == package.package_files


def test_package_directories_and_files_with_existing_stuff(mirror):
    pkg_name = 'foo'
    for path in ['packages/2.4',
                 'packages/any']:
        path = os.path.join(mirror.webdir, path, pkg_name[0], pkg_name)
        os.makedirs(path)
        filename = os.path.join(path, pkg_name+'.zip')
        open(filename, 'wb')
    package = Package(pkg_name, 10, mirror)
    dirs = sorted(package.package_directories)
    dirs = [x.replace(mirror.webdir, '') for x in dirs]
    assert dirs == ['/packages/2.4/f/foo', '/packages/any/f/foo']
    files = sorted(package.package_files)
    files = [x.replace(mirror.webdir, '') for x in files]
    assert files == ['/packages/2.4/f/foo/foo.zip',
                     '/packages/any/f/foo/foo.zip']


def test_package_sync_404_json_info_deletes_package(mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = {}

    response = mock.Mock()
    response.status_code = 404
    requests.prepare(HTTPError(response=response), 0)

    paths = ['web/packages/2.4/f/foo/foo.zip', 'web/simple/foo/index.html']
    touch_files(paths)

    package = Package('foo', 10, mirror)
    package.sync()

    for path in paths:
        path = os.path.join(path)
        assert not os.path.exists(path)


def test_package_sync_gives_up_after_3_stale_responses(
        caplog, mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = []

    requests.prepare('the simple page', '10')
    requests.prepare('the simple page', '10')
    requests.prepare('the simple page', '10')
    requests.prepare('the simple page', '10')

    package = Package('foo', 11, mirror)
    package.sleep_on_stale = 0

    mirror.queue = mock.Mock()

    package.sync()
    assert not mirror.errors
    assert package.tries == 1

    package.sync()
    assert package.tries == 2
    assert not mirror.errors

    package.sync()
    assert package.tries == 3
    assert mirror.errors
    assert mirror.queue.put.call_count == 2

    assert 'not updating. Giving up' in caplog.text()


def test_package_sync_no_releases_deletes_package_race_condition(
        mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = []
    response = mock.Mock()
    response.status_code = 404
    requests.prepare(HTTPError(response=response), 0)

    # web/simple/foo/index.html is always expected to exist. we don't fail if
    # it doesn't, though. Good for testing the race condition in the delete
    # function.
    paths = ['web/packages/2.4/f/foo/foo.zip']
    touch_files(paths)

    package = Package('foo', 10, mirror)
    package.sync()

    for path in paths:
        path = os.path.join(path)
        assert not os.path.exists(path)


def test_package_sync_with_release_no_files_syncs_simple_page(
        mirror, requests):

    requests.prepare({'releases': {}}, '10')
    requests.prepare('the simple page', '10')

    mirror.packages_to_sync = {'foo': 10}
    package = Package('foo', 10, mirror)
    package.sync()

    assert open('web/simple/foo/index.html').read() == 'the simple page'


def test_package_sync_with_canonical_simple_page(mirror, requests):

    requests.prepare({'releases': {}}, '10')
    requests.prepare('the simple page', '10')

    mirror.packages_to_sync = {'Foo': 10}
    package = Package('Foo', 10, mirror)
    package.sync()

    assert open('web/simple/foo/index.html').read() == 'the simple page'


def test_package_sync_simple_page_with_existing_dir(mirror, requests):
    requests.prepare({'releases': {'0.1': []}}, '10')
    requests.prepare('the simple page', '10')

    mirror.packages_to_sync = {'foo': 10}
    package = Package('foo', 10, mirror)
    os.makedirs(package.simple_directory)
    package.sync()

    assert open('web/simple/foo/index.html').read() == 'the simple page'


def test_package_sync_with_error_keeps_it_on_todo_list(
        mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = []

    requests.side_effect = Exception

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', 10, mirror)
    package.sync()
    assert 'foo' in mirror.packages_to_sync


def test_package_sync_downloads_release_file(mirror, requests):
    requests.prepare(
        {'releases': {
            '0.1': [
                {'url': 'https://pypi.example.com/packages/any/f/foo/foo.zip',
                 'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]}}, 10)
    requests.prepare('the release content', 10)

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', 10, mirror)
    package.sync()

    assert open('web/packages/any/f/foo/foo.zip').read() == (
        'the release content')


def test_package_download_rejects_non_package_directory_links(mirror):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {'url': 'https://pypi.example.com/foo/bar/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', 10, mirror)
    package.sync()
    assert mirror.errors
    assert 'foo' in mirror.packages_to_sync
    assert not os.path.exists('web/foo/bar/foo/foo.zip')


def test_sync_deletes_superfluous_files_on_deleting_mirror(mirror, requests):
    touch_files(['web/packages/2.4/f/foo/foo.zip'])

    requests.prepare({'releases': {'0.1': []}}, 10)

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', 10, mirror)
    package.sync()

    assert not os.path.exists('web/packages/2.4/f/foo/foo.zip')


def test_sync_keeps_superfluous_files_on_nondeleting_mirror(mirror, requests):
    touch_files(['web/packages/2.4/f/foo/foo.zip'])

    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = []
    mirror.delete_packages = False

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', 10, mirror)
    package.sync()

    assert os.path.exists('web/packages/2.4/f/foo/foo.zip')


def test_package_sync_replaces_mismatching_local_files(mirror, requests):
    requests.prepare(
        {'releases': {
            '0.1': [
                {'url': 'https://pypi.example.com/packages/any/f/foo/foo.zip',
                 'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]}}, 10)
    requests.prepare('the release content', 10)

    os.makedirs('web/packages/any/f/foo')
    with open('web/packages/any/f/foo/foo.zip', 'wb') as f:
        f.write(b'this is not the release content')

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', 10, mirror)
    package.sync()

    assert open('web/packages/any/f/foo/foo.zip').read() == (
        'the release content')


def test_package_sync_does_not_touch_existing_local_file(
        mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {'url': 'https://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    requests.prepare('the release content', 10)

    os.makedirs('web/packages/any/f/foo')
    with open('web/packages/any/f/foo/foo.zip', 'wb') as f:
        f.write(b'the release content')
    old_stat = os.stat('web/packages/any/f/foo/foo.zip')

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', 10, mirror)
    package.sync()

    new_stat = os.stat('web/packages/any/f/foo/foo.zip')
    assert old_stat == new_stat


def test_sync_incorrect_download_with_current_serial_fails(
        mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {'url': 'https://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    requests.prepare('not release content', 10)

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', 10, mirror)
    package.sync()

    assert not os.path.exists('web/packages/any/f/foo/foo.zip')
    assert mirror.errors


def test_sync_incorrect_download_with_old_serials_retries(
        mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {'url': 'https://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    requests.prepare('not release content', 9)

    mirror.packages_to_sync = set(['foo'])
    mirror.queue = Queue.Queue()
    package = Package('foo', 10, mirror)
    package.sync()

    assert not os.path.exists('web/packages/any/f/foo/foo.zip')
    assert not mirror.errors
    assert list(mirror.queue.queue) == [package]


def test_sync_does_not_fail_on_package_data_too_new(mirror, requests):
    requests.prepare(
        {'releases': {
            '0.1': [
                {'url': 'https://pypi.example.com/packages/any/f/foo/foo.zip',
                 'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]}}, 10)
    requests.prepare('not release content', 11)
    requests.prepare('the simple page', '10')

    mirror.packages_to_sync = dict(foo=10)
    package = Package('foo', 10, mirror)
    package.sync()

    assert not os.path.exists('web/packages/any/f/foo/foo.zip')

    assert open('web/simple/foo/index.html').read() == 'the simple page'


def test_sync_deletes_serversig(mirror, requests):
    requests.prepare({'releases': {'0.1': []}}, '10')
    requests.prepare('the simple page', '10')

    mirror.packages_to_sync = {'foo': 10}
    package = Package('foo', 10, mirror)
    os.makedirs(package.simple_directory)
    os.makedirs(os.path.join(package.mirror.webdir, 'serversig'))
    open(package.serversig_file, "w").close()

    assert os.path.exists(package.serversig_file)

    package.sync()

    assert open('web/simple/foo/index.html').read() == 'the simple page'
    assert not os.path.exists(package.serversig_file)

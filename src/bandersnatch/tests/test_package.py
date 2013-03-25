from bandersnatch.package import Package
import mock
import os.path

 
def test_package_directories_and_files_on_empty_mirror(mirror):
    package = Package('foo', mirror)
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
    package = Package(pkg_name, mirror)
    dirs = sorted(package.package_directories)
    dirs = [x.replace(mirror.webdir, '') for x in dirs]
    assert dirs == ['/packages/2.4/f/foo', '/packages/any/f/foo']
    files = sorted(package.package_files)
    files = [x.replace(mirror.webdir, '') for x in files]
    assert files == ['/packages/2.4/f/foo/foo.zip',
                     '/packages/any/f/foo/foo.zip']


def test_package_sync_no_releases_deletes_package(mirror):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = []

    paths = ['web/packages/2.4/f/foo/foo.zip',
             'web/serversig/foo',
             'web/simple/foo/index.html']
    for path in paths:
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        open(path, 'wb')

    package = Package('foo', mirror)
    package.sync()

    for path in paths:
        path = os.path.join(path)
        assert not os.path.exists(path)


def test_package_sync_no_releases_deletes_package_race_condition(mirror):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = []

    # web/simple/foo/index.html is always expected to exist. we don't fail if it doesn't, though.
    paths = ['web/packages/2.4/f/foo/foo.zip',
             'web/serversig/foo']
    for path in paths:
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        open(path, 'wb')

    package = Package('foo', mirror)
    package.sync()

    for path in paths:
        path = os.path.join(path)
        assert not os.path.exists(path)


def test_package_sync_with_release_no_files_syncs_simple_page(
        mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = []

    simple_page_response = mock.Mock()
    simple_page_response.content = 'the simple page'
    serversig_response = mock.Mock()
    serversig_response.content = 'the server signature'

    responses = iter([simple_page_response, serversig_response])
    requests.side_effect = lambda *args, **kw: responses.next()

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', mirror)
    package.sync()

    assert open('web/simple/foo/index.html').read() == 'the simple page'
    assert open('web/serversig/foo').read() == 'the server signature'


def test_package_sync_with_error_keeps_it_on_todo_list(
        mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = []

    requests.side_effect = Exception

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', mirror)
    package.sync()
    assert 'foo' in mirror.packages_to_sync


def test_package_sync_downloads_release_file(
        mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {'url': 'http://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    release_download = mock.Mock()
    release_download.iter_content.return_value = iter('the release content')

    requests.return_value = release_download

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', mirror)
    package.sync()

    assert open('web/packages/any/f/foo/foo.zip').read() == 'the release content'


def test_package_download_rejects_non_package_directory_links(
        mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {'url': 'http://pypi.example.com/foo/bar/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', mirror)
    package.sync()
    assert mirror.errors
    assert 'foo' in mirror.packages_to_sync
    assert not os.path.exists('web/foo/bar/foo/foo.zip')


def test_sync_deletes_superfluous_files_on_deleting_mirror(mirror, requests):
    paths = ['web/packages/2.4/f/foo/foo.zip']
    for path in paths:
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        open(path, 'wb')

    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = []

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', mirror)
    package.sync()

    assert not os.path.exists('web/packages/2.4/f/foo/foo.zip')


def test_sync_keeps_superfluous_files_on_nondeleting_mirror(mirror, requests):
    paths = ['web/packages/2.4/f/foo/foo.zip']
    for path in paths:
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        open(path, 'wb')

    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = []
    mirror.delete_packages = False

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', mirror)
    package.sync()

    assert os.path.exists('web/packages/2.4/f/foo/foo.zip')


def test_package_sync_replaces_mismatching_local_files(
        mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {'url': 'http://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    release_download = mock.Mock()
    release_download.iter_content.return_value = iter('the release content')

    requests.return_value = release_download

    os.makedirs('web/packages/any/f/foo')
    with open('web/packages/any/f/foo/foo.zip', 'wb') as f:
        f.write('this is not the release content')

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', mirror)
    package.sync()

    assert open('web/packages/any/f/foo/foo.zip').read() == 'the release content'


def test_package_sync_does_not_touch_existing_local_file(
        mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {'url': 'http://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    release_download = mock.Mock()
    release_download.iter_content.return_value = iter('the release content')

    requests.return_value = release_download

    os.makedirs('web/packages/any/f/foo')
    with open('web/packages/any/f/foo/foo.zip', 'wb') as f:
        f.write('the release content')
    old_stat = os.stat('web/packages/any/f/foo/foo.zip')

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', mirror)
    package.sync()

    new_stat = os.stat('web/packages/any/f/foo/foo.zip')
    assert old_stat == new_stat


def test_sync_does_not_keep_download_with_incorrect_checksum(
        mirror, requests):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls = mock.Mock()
    mirror.master.release_urls.return_value = [
        {'url': 'http://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    release_download = mock.Mock()
    release_download.iter_content.return_value = iter('not the release content')
    requests.return_value = release_download

    mirror.packages_to_sync = set(['foo'])
    package = Package('foo', mirror)
    package.sync()

    assert not os.path.exists('web/packages/any/f/foo/foo.zip')

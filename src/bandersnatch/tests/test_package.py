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
    dirs = package.package_directories
    dirs = [x.replace(mirror.webdir, '') for x in dirs]
    assert dirs == ['/packages/2.4/f/foo', '/packages/any/f/foo']
    files = package.package_files
    files = [x.replace(mirror.webdir, '') for x in files]
    assert files == ['/packages/2.4/f/foo/foo.zip',
                     '/packages/any/f/foo/foo.zip']


def test_package_sync_no_releases_deletes_package(mirror):
    mirror.master.package_releases = mock.Mock()
    mirror.master.package_releases.return_value = []

    paths = ['packages/2.4/f/foo/foo.zip',
             'serversig/foo',
             'simple/foo/index.html']
    for path in paths:
        path = os.path.join(mirror.webdir, path)
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        open(path, 'wb')

    package = Package('foo', mirror)
    package.sync()

    for path in paths:
        path = os.path.join(mirror.webdir, path)
        assert not os.path.exists(path)

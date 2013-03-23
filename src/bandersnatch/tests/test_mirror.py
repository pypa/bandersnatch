from bandersnatch import utils
from bandersnatch.mirror import Mirror
import mock
import os.path
import pytest


def test_limit_workers():
    try:
        Mirror(None, None, workers=51)
    except ValueError:
        pass


def test_mirror_with_same_homedir_needs_lock(mirror, tmpdir):
    try:
        Mirror(mirror.homedir, mirror.master)
    except RuntimeError:
        pass
    Mirror(os.path.join(mirror.homedir+'/test'), mirror.master)


def test_mirror_empty_master_gets_index(mirror, master_mock, requests):
    mirror.master = master_mock
    mirror.master.list_packages.return_value = []
    mirror.master.get_current_serial.return_value = 1
    
    simple_index_page = mock.Mock()
    simple_index_page.content = 'the index page'
    requests.return_value = simple_index_page

    mirror.synchronize()

    assert """\
/.lock
/status
/web
/web/last-modified
/web/local-stats
/web/local-stats/days
/web/packages
/web/serversig
/web/simple
/web/simple/index.html""" == utils.find(mirror.homedir)
    assert open('web/simple/index.html').read() == 'the index page'
    assert open('status').read() == '1'


def test_mirror_empty_resume_from_todo_list(mirror, master_mock, requests):
    mirror.master = master_mock
    mirror.master.get_current_serial.return_value = 2
    
    simple_index_page = mock.Mock()
    simple_index_page.content = 'the index page'
    requests.return_value = simple_index_page

    with open('todo', 'w') as todo:
        todo.write('1\n')

    mirror.synchronize()

    assert """\
/.lock
/status
/web
/web/last-modified
/web/local-stats
/web/local-stats/days
/web/packages
/web/serversig
/web/simple
/web/simple/index.html""" == utils.find(mirror.homedir)
    assert open('web/simple/index.html').read() == 'the index page'
    assert open('status').read() == '1'


def test_mirror_empty_sync_from_changelog(mirror, master_mock, requests):
    mirror.master = master_mock
    mirror.master.get_current_serial.return_value = 2
    mirror.master.changed_packages.return_value = ([], 3)

    simple_index_page = mock.Mock()
    simple_index_page.content = 'the index page'
    requests.return_value = simple_index_page
    
    with open('status', 'w') as status:
        status.write('1')
    with open('web/simple/index.html', 'w') as simple:
        simple.write('old simple file')

    mirror._bootstrap()
    mirror.synchronize()

    assert open('web/simple/index.html').read() == 'old simple file'
    assert open('status').read() == '3'


def test_mirror_empty_sync_with_errors_keeps_index_and_status(mirror, master_mock, requests):
    mirror.master = master_mock
    mirror.master.get_current_serial.return_value = 2
    mirror.master.changed_packages.return_value = ([], 3)

    simple_index_page = mock.Mock()
    simple_index_page.content = 'the index page'
    requests.return_value = simple_index_page
    
    with open('status', 'w') as status:
        status.write('1')
    with open('web/simple/index.html', 'w') as simple:
        simple.write('old simple file')

    mirror._bootstrap()
    mirror.errors = True
    mirror.synchronize()

    assert open('web/simple/index.html').read() == 'old simple file'
    assert open('status').read() == '1'


def test_mirror_sync_package(mirror, master_mock, requests):
    mirror.master = master_mock
    mirror.master.get_current_serial.return_value = 1
    mirror.master.list_packages.return_value = ['foo']
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls.return_value = [
        {'url': 'http://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    release_download = mock.Mock()
    release_download.iter_content.return_value = iter('the release content')
    simple_page = mock.Mock()
    simple_page.content = 'the simple page'
    serversig = mock.Mock()
    serversig.content = 'the server signature'
    simple_index_page = mock.Mock()
    simple_index_page.content = 'the index page'

    responses = iter([release_download, simple_page, serversig, simple_index_page])
    requests.side_effect = lambda *args, **kw: responses.next()

    mirror.synchronize()

    assert """\
/.lock
/status
/web/last-modified
/web/packages/any/f/foo/foo.zip
/web/serversig/foo
/web/simple/foo/index.html
/web/simple/index.html""" == utils.find(mirror.homedir, dirs=False)
    assert open('web/simple/index.html').read() == 'the index page'
    assert open('status').read() == '1'


def test_mirror_sync_package_error_no_early_exit(mirror, master_mock, requests):
    mirror.master = master_mock
    mirror.master.get_current_serial.return_value = 1
    mirror.master.list_packages.return_value = ['foo']
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls.return_value = [
        {'url': 'http://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    release_download = mock.Mock()
    release_download.iter_content.return_value = iter('the release content')
    simple_page = mock.Mock()
    simple_page.content = 'the simple page'
    serversig = mock.Mock()
    serversig.content = 'the server signature'
    simple_index_page = mock.Mock()
    simple_index_page.content = 'the index page'

    responses = iter([release_download, simple_page, serversig, simple_index_page])
    requests.side_effect = lambda *args, **kw: responses.next()

    mirror.errors = True
    mirror.synchronize()

    assert """\
/.lock
/todo
/web/packages/any/f/foo/foo.zip
/web/serversig/foo
/web/simple/foo/index.html
/web/simple/index.html""" == utils.find(mirror.homedir, dirs=False)
    assert open('web/simple/index.html').read() == 'the index page'


def test_mirror_sync_package_error_early_exit(mirror, master_mock, requests):
    mirror.master = master_mock
    mirror.master.get_current_serial.return_value = 1
    mirror.master.list_packages.return_value = ['foo']
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls.return_value = [
        {'url': 'http://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    release_download = mock.Mock()
    release_download.iter_content.return_value = iter('the release content')
    simple_page = mock.Mock()
    simple_page.content = 'the simple page'
    serversig = mock.Mock()
    serversig.content = 'the server signature'
    simple_index_page = mock.Mock()
    simple_index_page.content = 'the index page'

    responses = iter([release_download, simple_page, serversig, simple_index_page])
    requests.side_effect = lambda *args, **kw: responses.next()

    with open('web/simple/index.html', 'wb') as index:
        index.write('old index')
    mirror.errors = True
    mirror.stop_on_error = True
    with pytest.raises(SystemExit):
        mirror.synchronize()

    assert """\
/.lock
/todo
/web/packages/any/f/foo/foo.zip
/web/serversig/foo
/web/simple/foo/index.html
/web/simple/index.html""" == utils.find(mirror.homedir, dirs=False)
    assert open('web/simple/index.html').read() == 'old index'

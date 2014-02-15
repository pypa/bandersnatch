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


def test_mirror_loads_serial(tmpdir):
    with open(str(tmpdir/'generation'), 'w') as generation:
        generation.write('2')
    with open(str(tmpdir/'status'), 'w') as status:
        status.write('1234')
    m = Mirror(str(tmpdir), mock.Mock())
    assert m.synced_serial == 1234


def test_mirror_removes_empty_todo_list(tmpdir):
    with open(str(tmpdir/'generation'), 'w') as generation:
        generation.write('2')
    with open(str(tmpdir/'status'), 'w') as status:
        status.write('1234')
    with open(str(tmpdir/'todo'), 'w') as status:
        status.write('')
    Mirror(str(tmpdir), mock.Mock())
    assert not os.path.exists(str(tmpdir/'todo'))


def test_mirror_removes_broken_todo_list(tmpdir):
    with open(str(tmpdir/'generation'), 'w') as generation:
        generation.write('2')
    with open(str(tmpdir/'status'), 'w') as status:
        status.write('1234')
    with open(str(tmpdir/'todo'), 'w') as status:
        status.write('foo')
    Mirror(str(tmpdir), mock.Mock())
    assert not os.path.exists(str(tmpdir/'todo'))


def test_mirror_removes_old_status_and_todo_inits_generation(tmpdir):
    with open(str(tmpdir/'status'), 'w') as status:
        status.write('1234')
    with open(str(tmpdir/'todo'), 'w') as status:
        status.write('foo')
    Mirror(str(tmpdir), mock.Mock())
    assert not os.path.exists(str(tmpdir/'todo'))
    assert not os.path.exists(str(tmpdir/'status'))
    assert open(str(tmpdir/'generation')).read().strip() == '2'


def test_mirror_with_same_homedir_needs_lock(mirror, tmpdir):
    try:
        Mirror(mirror.homedir, mirror.master)
    except RuntimeError:
        pass
    Mirror(os.path.join(mirror.homedir+'/test'), mirror.master)


def test_mirror_empty_master_gets_index(mirror, master_mock):
    mirror.master = master_mock
    mirror.master.all_packages.return_value = {}

    mirror.synchronize()

    assert """\
/last-modified
/local-stats
/local-stats/days
/packages
/serversig
/simple
/simple/index.html""" == utils.find(mirror.webdir)
    assert open('web/simple/index.html').read() == """\
<html><head><title>Simple Index</title></head><body>
</body></html>"""
    assert open('status').read() == '0'


def test_mirror_empty_resume_from_todo_list(mirror, master_mock):
    mirror.master = master_mock
    mirror.master.package_releases.return_value = []

    with open('todo', 'w') as todo:
        todo.write('20\nfoobar 10')

    mirror.synchronize()

    assert """\
/.lock
/generation
/status
/web
/web/last-modified
/web/local-stats
/web/local-stats/days
/web/packages
/web/serversig
/web/simple
/web/simple/index.html""" == utils.find(mirror.homedir)
    assert open('web/simple/index.html').read() == """\
<html><head><title>Simple Index</title></head><body>
</body></html>"""
    assert open('status').read() == '20'


def test_mirror_sync_package(mirror, master_mock):
    mirror.master = master_mock
    mirror.master.all_packages.return_value = {'foo': 1}
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls.return_value = [
        {'url': 'https://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    release_download = mock.Mock()
    release_download.headers = {'X-PYPI-LAST-SERIAL': 1}
    release_download.iter_content.return_value = iter('the release content')
    simple_page = mock.Mock()
    simple_page.content = 'the simple page'
    serversig = mock.Mock()
    serversig.content = 'the server signature'

    responses = iter([release_download,
                      simple_page,
                      serversig])
    master_mock.get.side_effect = lambda *args, **kw: responses.next()

    mirror.synchronize()

    assert """\
/last-modified
/packages/any/f/foo/foo.zip
/serversig/foo
/simple/foo/index.html
/simple/index.html""" == utils.find(mirror.webdir, dirs=False)
    assert open('web/simple/index.html').read() == """\
<html><head><title>Simple Index</title></head><body>
<a href="foo/">foo</a><br/>
</body></html>"""
    assert open('status').read() == '1'


def test_mirror_sync_package_with_retry(mirror, master_mock):
    mirror.master = master_mock
    mirror.master.all_packages.return_value = {'foo': 1}
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls.return_value = [
        {'url': 'https://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    release_download_stale = mock.Mock()
    release_download_stale.headers = {'X-PYPI-LAST-SERIAL': 0}
    release_download_stale.iter_content.return_value = iter(
        'not release content')

    release_download = mock.Mock()
    release_download.headers = {'X-PYPI-LAST-SERIAL': 1}
    release_download.iter_content.return_value = iter('the release content')
    simple_page = mock.Mock()
    simple_page.content = 'the simple page'
    serversig = mock.Mock()
    serversig.content = 'the server signature'

    responses = iter([lambda: release_download_stale,
                      lambda: release_download,
                      lambda: simple_page,
                      lambda: serversig])
    master_mock.get.side_effect = lambda *args, **kw: responses.next()()

    mirror.synchronize()

    assert """\
/last-modified
/packages/any/f/foo/foo.zip
/serversig/foo
/simple/foo/index.html
/simple/index.html""" == utils.find(mirror.webdir, dirs=False)
    assert open('web/simple/index.html').read() == """\
<html><head><title>Simple Index</title></head><body>
<a href="foo/">foo</a><br/>
</body></html>"""

    assert open('status').read() == '1'


def test_mirror_sync_package_error_no_early_exit(
        mirror, master_mock):
    mirror.master = master_mock
    mirror.master.all_packages.return_value = {'foo': 1}
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls.return_value = [
        {'url': 'https://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    release_download = mock.Mock()
    release_download.headers = {'X-PYPI-LAST-SERIAL': 1}
    release_download.iter_content.return_value = iter('the release content')
    simple_page = mock.Mock()
    simple_page.content = 'the simple page'
    serversig = mock.Mock()
    serversig.content = 'the server signature'

    responses = iter([release_download,
                      simple_page,
                      serversig])
    master_mock.get.side_effect = lambda *args, **kw: responses.next()

    mirror.errors = True
    mirror.synchronize()

    assert """\
/.lock
/generation
/todo
/web/packages/any/f/foo/foo.zip
/web/serversig/foo
/web/simple/foo/index.html
/web/simple/index.html""" == utils.find(mirror.homedir, dirs=False)
    assert open('web/simple/index.html').read() == """\
<html><head><title>Simple Index</title></head><body>
<a href="foo/">foo</a><br/>
</body></html>"""

    assert open('todo').read() == '1\n'


def test_mirror_sync_package_error_early_exit(mirror, master_mock):
    mirror.master = master_mock
    mirror.master.all_packages.return_value = {'foo': 1}
    mirror.master.package_releases.return_value = ['0.1']
    mirror.master.release_urls.return_value = [
        {'url': 'https://pypi.example.com/packages/any/f/foo/foo.zip',
         'md5_digest': 'b6bcb391b040c4468262706faf9d3cce'}]

    release_download = mock.Mock()
    release_download.headers = {'X-PYPI-LAST-SERIAL': 1}
    release_download.iter_content.return_value = iter('the release content')
    simple_page = mock.Mock()
    simple_page.content = 'the simple page'
    serversig = mock.Mock()
    serversig.content = 'the server signature'

    responses = iter([release_download,
                      simple_page,
                      serversig])
    master_mock.get.side_effect = lambda *args, **kw: responses.next()

    with open('web/simple/index.html', 'wb') as index:
        index.write('old index')
    mirror.errors = True
    mirror.stop_on_error = True
    with pytest.raises(SystemExit):
        mirror.synchronize()

    assert """\
/.lock
/generation
/todo
/web/packages/any/f/foo/foo.zip
/web/serversig/foo
/web/simple/foo/index.html
/web/simple/index.html""" == utils.find(mirror.homedir, dirs=False)
    assert open('web/simple/index.html').read() == 'old index'
    assert open('todo').read() == '1\n'


def test_mirror_serial_current_no_sync_of_packages_and_index_page(
        mirror, master_mock):
    mirror.master = master_mock
    mirror.master.changed_packages.return_value = {}
    mirror.synced_serial = 1

    mirror.synchronize()

    assert """\
/last-modified""" == utils.find(mirror.webdir, dirs=False)

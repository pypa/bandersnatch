from bandersnatch.main import main
import bandersnatch.mirror
import mock
import os.path
import pytest
import sys


def test_main_help(capfd):
    sys.argv = ['bandersnatch', '--help']
    with pytest.raises(SystemExit):
        main()
    out, err = capfd.readouterr()
    assert out.startswith('usage: bandersnatch')
    assert '' == err


def test_main_create_config(caplog, tmpdir):
    sys.argv = ['bandersnatch', '-c', str(tmpdir / 'bandersnatch.conf'),
                'mirror']
    with pytest.raises(SystemExit):
        main()
    assert 'creating default config' in caplog.text()
    assert os.path.exists(str(tmpdir / 'bandersnatch.conf'))


def test_main_cant_create_config(caplog, tmpdir):
    sys.argv = ['bandersnatch',
                '-c', str(tmpdir / 'foo' / 'bandersnatch.conf'),
                'mirror']
    with pytest.raises(SystemExit):
        main()
    assert 'creating default config' in caplog.text()
    assert 'Could not create config file' in caplog.text()
    assert not os.path.exists(str(tmpdir / 'bandersnatch.conf'))


def test_main_reads_config_values(mirror_mock):
    config = os.path.dirname(bandersnatch.__file__) + '/default.conf'
    sys.argv = ['bandersnatch', '-c', config, 'mirror']
    assert os.path.exists(config)
    assert isinstance(bandersnatch.mirror.Mirror, mock.Mock)
    main()
    (homedir, master), kwargs = mirror_mock.call_args_list[0]
    assert '/srv/pypi' == homedir
    assert isinstance(master, bandersnatch.master.Master)
    assert {'delete_packages': True,
            'stop_on_error': False,
            'workers': 3} == kwargs
    assert mirror_mock().synchronize.called


@pytest.fixture
def tmpconfig(tmpdir):
    default = os.path.dirname(bandersnatch.__file__) + '/default.conf'
    with open(str(tmpdir/'bandersnatch.conf'), 'w') as f:
        config = open(default).read()
        config = config.replace('/srv/pypi', str(tmpdir/'pypi'))
        f.write(config)
    return tmpdir


def test_main_stats_requires_mirror_dir(caplog, tmpconfig):
    sys.argv = ['bandersnatch', '-c', str(tmpconfig / 'bandersnatch.conf'),
                'update-stats']
    with pytest.raises(SystemExit):
        main()
    assert '/pypi does not exist' in caplog.text()
    assert 'Please run' in caplog.text()


def test_main_stats_requires_web_dir(caplog, tmpconfig):
    sys.argv = ['bandersnatch', '-c', str(tmpconfig / 'bandersnatch.conf'),
                'update-stats']
    os.mkdir(str(tmpconfig/'pypi'))
    with pytest.raises(SystemExit):
        main()
    assert '/web does not exist' in caplog.text()
    assert 'Is this a mirror?' in caplog.text()


def test_main_stats_creates_stats_dir(caplog, tmpconfig):
    sys.argv = ['bandersnatch', '-c', str(tmpconfig / 'bandersnatch.conf'),
                'update-stats']
    os.mkdir(str(tmpconfig/'pypi'))
    os.mkdir(str(tmpconfig/'pypi/web'))
    main()
    assert os.path.exists(str(tmpconfig/'pypi/web/local-stats'))
    assert os.path.exists(str(tmpconfig/'pypi/web/local-stats/days'))
    assert 'Creating statistics directory' in caplog.text()


def test_main_stats_uses_existing_dirs(caplog, tmpconfig):
    sys.argv = ['bandersnatch', '-c', str(tmpconfig / 'bandersnatch.conf'),
                'update-stats']
    os.mkdir(str(tmpconfig/'pypi'))
    os.mkdir(str(tmpconfig/'pypi/web'))
    os.mkdir(str(tmpconfig/'pypi/web/local-stats'))
    os.mkdir(str(tmpconfig/'pypi/web/local-stats/days'))
    main()
    assert 'Creating statistics directory' not in caplog.text()

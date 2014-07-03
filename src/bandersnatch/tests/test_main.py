from bandersnatch.main import main
import bandersnatch.mirror
import logging.config
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


def test_main_reads_log_config_value(mirror_mock, logging_mock, tmpconfig):
    config = str(tmpconfig/'with-logging.conf')
    sys.argv = ['bandersnatch', '-c', config, 'mirror']
    assert os.path.exists(config)
    assert isinstance(bandersnatch.mirror.Mirror, mock.Mock)
    assert isinstance(logging.config.fileConfig, mock.Mock)
    main()
    (log_config, kwargs) = logging_mock.call_args_list[0]
    assert log_config == (str(tmpconfig/'bandersnatch-log.conf'),)
    assert mirror_mock().synchronize.called


@pytest.fixture
def tmpconfig(tmpdir):
    default = os.path.dirname(bandersnatch.__file__) + '/default.conf'
    config = open(default).read()
    config = config.replace('/srv/pypi', str(tmpdir/'pypi'))
    with open(str(tmpdir/'bandersnatch.conf'), 'w') as f:
        f.write(config)
    config = config.replace('; log-config', 'log-config')
    config = config.replace(
        '/etc/bandersnatch-log.conf',
        str(tmpdir/'bandersnatch-log.conf'))
    with open(str(tmpdir/'with-logging.conf'), 'w') as f:
        f.write(config)
    return tmpdir

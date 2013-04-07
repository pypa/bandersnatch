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

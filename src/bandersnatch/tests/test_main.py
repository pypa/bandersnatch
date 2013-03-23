from bandersnatch.main import main
import bandersnatch.mirror
import mock
import os.path
import pytest
import sys


def test_main_help(capsys):
    sys.argv = ['bsn-mirror', '--help']
    with pytest.raises(SystemExit):
        main()
    out, err = capsys.readouterr()
    assert out.startswith('usage: bsn-mirror')
    assert '' == err


def test_main_create_config(capsys, tmpdir):
    sys.argv = ['bsn-mirror', '-c', str(tmpdir / 'bandersnatch.conf')]
    with pytest.raises(SystemExit):
        main()
    out, err = capsys.readouterr()
    assert 'creating default config' in err
    assert os.path.exists(str(tmpdir / 'bandersnatch.conf'))


def test_main_cant_create_config(capsys, tmpdir):
    sys.argv = ['bsn-mirror', '-c', str(tmpdir / 'foo' / 'bandersnatch.conf')]
    with pytest.raises(SystemExit):
        main()
    out, err = capsys.readouterr()
    assert 'creating default config' in err
    assert 'Could not create config file' in err
    assert not os.path.exists(str(tmpdir / 'bandersnatch.conf'))


def test_main_reads_config_values(capsys, mirror_mock):
    config = os.path.dirname(bandersnatch.__file__) + '/default.conf'
    sys.argv = ['bsn-mirror', '-c', config]
    assert os.path.exists(config)
    assert isinstance(bandersnatch.mirror.Mirror, mock.Mock)
    main()
    out, err = capsys.readouterr()
    (homedir, master), kwargs = mirror_mock.call_args_list[0]
    assert '/srv/pypi' == homedir
    assert isinstance(master, bandersnatch.master.Master)
    assert {'delete_packages': True, 'stop_on_error': False, 'workers': 3} == kwargs
    assert mirror_mock().synchronize.called

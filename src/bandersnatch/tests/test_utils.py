from bandersnatch.utils import hash, rewrite
import os
import os.path
import pytest
import six


if six.PY2:
    expected_octal_perms = "0100644"
else:
    expected_octal_perms = "0o100644"


def test_hash():
    sample = os.path.join(os.path.dirname(__file__), 'sample')
    assert hash(sample, function='md5') == '125765989403df246cecb48fa3e87ff8'
    assert hash(sample, function='sha256') == ('95c07c174663ebff531eed59b326eb'
                                               'b3fa95f418f680349fc33b07dfbcf2'
                                               '9f18')
    assert hash(sample) == ('95c07c174663ebff531eed59b326ebb3fa95f418f680349fc'
                            '33b07dfbcf29f18')


def test_rewrite(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    with open('sample', 'w') as f:
        f.write('bsdf')
    with rewrite('sample') as f:
        f.write('csdf')
    assert open('sample').read() == 'csdf'
    mode = os.stat('sample').st_mode
    assert oct(mode) == expected_octal_perms


def test_rewrite_fails(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    with open('sample', 'w') as f:
        f.write('bsdf')
    with pytest.raises(Exception):
        with rewrite('sample') as f:
            f.write('csdf')
            raise Exception()
    assert open('sample').read() == 'bsdf'


def test_rewrite_nonexisting_file(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    with rewrite('sample') as f:
        f.write('csdf')
    assert open('sample').read() == 'csdf'

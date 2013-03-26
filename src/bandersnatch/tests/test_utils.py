from bandersnatch.utils import hash, rewrite
import os
import os.path
import pytest


def test_hash():
    sample = os.path.join(os.path.dirname(__file__), 'sample')
    assert hash(sample) == '125765989403df246cecb48fa3e87ff8'


def test_rewrite(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    with open('sample', 'w') as f:
        f.write('bsdf')
    with rewrite('sample') as f:
        f.write('csdf')
    assert open('sample').read() == 'csdf'
    mode = os.stat('sample').st_mode
    assert oct(mode) == "0100644"


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

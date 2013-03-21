from bandersnatch.utils import hash
import os.path

def test_hash():
    sample = os.path.join(os.path.dirname(__file__), 'sample')
    assert hash(sample) == '125765989403df246cecb48fa3e87ff8'

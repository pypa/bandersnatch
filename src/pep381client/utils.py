import hashlib

def hash(path, function='md5'):
    h = getattr(hashlib, function)()
    for line in open(path):
        h.update(line)
    return h.hexdigest()

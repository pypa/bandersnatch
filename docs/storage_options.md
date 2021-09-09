# Storage options for bandersnatch

Bandersnatch was originally developed for POSIX file system. Bandersnatch now supports:

- POSIX / Windows filesystem (transparently via pathlib)
- [Amazon S3](https://aws.amazon.com/s3/)
- [Cannoical SwiftStack Storage](https://www.swiftstack.com/product/storage)

## Filesystem Support

This is the default mode for bandersnatch.

### Config Example

```ini
[mirror]
directory = /data/pypi/mirror
storage-backend = filesystem
# Optional index hashing to store simple HTML in directories
# Recommended as PyPI has a lot of packages these days
hash-index = true
```

### Serving your Mirror

Simple html is stored within the file system structure. Please use your
favorite http server such as Apache or NGINX. Refer to [Serving](serving.md) documentation about a NGINX Docker container option.

## Amazon S3

To enable S3 support the optional `s3` install must be done:

- `pip install bandersnatch[s3]`
- Add a `[s3]` section in the bandersnatch config file

### Config Example

```ini
[mirror]
# Place your s3 path here - e.g. /{bucket name}/{prefix}
directory = /my-s3-bucket/prefix
# Set storage-backend to s3
storage-backend = s3
# Provide s3 style path - e.g. /{bucket name}/{prefix}/{key}
diff-file = /your-s3-bucket/bucket-key

[s3]
# Optional Region name - can be empty if IAM are set
region_name = us-east-1
aws_access_key_id = your s3 access key
aws_secret_access_key = your s3 secret access key
# Use endpoint_url to indicate custom s3 endpoint e.g. like minio etc.
endpoint_url = endpoint url
# Optional manual signature version for compatibility
signature_version = s3v4
```

### Serving your Mirror

S3 Bandersnatch mirrors are designed to be served with s3 static sites and
can also be used with the Amazon CDN service or another CDN service.

## SwiftStack Storage

To enable SwiftStack support the optional `ssift` install must be done:

- `pip install bandersnatch[swift]`
- Add a `[swift]` section in the bandersnatch config file

### Config Example

```ini
[mirror]
# Place a local directory for temporary storage for downloads etc.
directory = /tmp/pypi-mirror
storage-backend = swift

[swift]
default_container = bandersnatch
```

### Serving your Mirror

Unknown. To be added.

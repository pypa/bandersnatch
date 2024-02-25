# Storage options for bandersnatch

Bandersnatch was originally developed for POSIX file system. Bandersnatch now supports:

- POSIX / Windows filesystem (transparently via pathlib)
- [Amazon S3](https://aws.amazon.com/s3/)
- [OpenStack Swift](https://docs.openstack.org/swift/latest/)

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

You will need an [AWS account](https://aws.amazon.com/console/) and an [S3 bucket](https://docs.aws.amazon.com/AmazonS3/latest/userguide/creating-bucket.html)

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

I assume you have already set up an AWS account and S3 bucket, and the Bandersnatch sync job has successfully ran.

### Enabling website hosting for the bucket

When you enable the website hosting for a bucket, this bucket can be viewed as static website. Using the s3 domain or your customized domain.

Please read Amazon documents to get [detailed instructions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/EnableWebsiteHosting.html)

Most cloud provider who provide a s3-compatible service will provide this service as well. Please consult to your service assistant to get detailed instructions.

### Use CloudFront or other cdn service to speed up the static mirror(optional)

If your mirror is targeted to global clients, you can use CloudFront or other CDN service to speed up the mirror.

Please read Amazon documents to get [detailed instructions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/website-hosting-cloudfront-walkthrough.html)

### Set redirect or url rewrite in CloudFront or other cdn(optional)

In most cases, packages and index pages are all inside `/my-s3-bucket/prefix/web`, if you set up a steps above, you should be able to use the mirror like this:

```shell
pip install -i my-s3-bucket.cloudfront.net/prefix/web/simple install django
```

But there are two main disadvantages:

1. The url is quite long and exposing the structure of bucket.
1. Users will be able to view all content in the bucket, including bandersnatch todo file and status file.

It is strongly recommended to set redirect or url rewrite for CDN. Please contact your service assistant for detailed instructions.

## OpenStack Swift

To enable Swift support the optional `swift` install must be done:

- `pip install bandersnatch[swift]`
- Add a `[swift]` section in the bandersnatch config file

### Config Example

```ini
[mirror]
directory = /prefix
storage-backend = swift

[swift]
default_container = bandersnatch
```

### Serving your Mirror

Requires that the cluster has [staticweb](https://docs.openstack.org/swift/latest/middleware.html#staticweb) enabled.

```shell
# Check that staticweb is enabled
swift capabilities | grep staticweb
# Make the container world-readable and enable pseudo-directory translation
swift post bandersnatch -r '.r:*' -m 'web-index: index.html'
```

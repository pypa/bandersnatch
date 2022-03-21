# Serving your Mirror

So if you've had a successful `bandersnatch mirror` run, you're now ready to serve
your mirror. Any webserver can do this, as long as it can serve the simple HTML and
packages directory that the HTML links to.

## BanderX

`banderx` is a very simple [NGINX](https://www.nginx.com/) docker image with a
sample config included. The example only does HTTP and expects you to do your
own HTTPS/TLS elsewhere.

- Default config is not setup for `hash_index = true` synced bandersnatch mirror
  - The *hash_index* serving config is in the example config and needs to be
    uncommented
  - It also sets the correct JSON MIME type for `/json` + `/pypi`

### Docker Build

- `cd src/banderx`
- `docker build -t banderx .`

### Docker Run

- `docker run --name bandersnatch_nginx --mount type=bind,source=/data/pypi/web,target=/data/pypi/web banderx`
- For custom config add:
  - `--mount type=bind,source=$PWD/nginx.conf,target=/config/nginx.conf`

### Bind Mount Nginx Config

If you want a different nginx config bind mount to:

- `/config/nginx.conf`

The config defaults for the mirror to be bind mounted to:

- `/data/pypi/web`

# BanderX

A very simple docker image with a sample config included. The example only does
HTTP and expects you to do your own HTTPS/TLS elsewhere.

- Default config is not setup for `hash_index = true` synced bandersnatch mirror
  - The config is in the example config and needs to be uncommented
  - It also sets the correct JSON MIME type for `/json` + `/pypi`

## Bind Mount Nginx Config

If you want a different nginx config bind mount to:

- `/config/nginx.conf`

## Docker Run

- `docker run --name bandersnatch_nginx --network host banderx`

## Docker Build

- `docker build -t banderx .`

# Bandersnatch with docker compose

Similar to [banderx](https://github.com/pypa/bandersnatch/tree/main/src/banderx) but with docker compose.

## Preparation

- alter the bandersnatch configuration (conf/bandersnatch.conf) to your desires
- alter the volume configuration inside the compose file to your desires
- alter the MTU in the compose file as 800 is very low, see explanation below.

Most of the time an MTU of 1500 is a good value, but depending on your landscape
this might be too high e.g. when working on nested virtualisation or software
defined networks. But it might also happen that your network allows jumbo frames
and then an MTU of 1500 is more like an artificial limitation. As stated, the
example took an MTU of 800 to make sure.

## Run (with docker-compose v2)

- `docker compose up -d`

## Caveats

Watch out for your docker MTU settings. Changing the MTU of the daemon is not going to help (see issue #1271).
Otherwise you might get error messages like these:

```
ERROR: Call to list_packages_with_serial @ https://pypi.org/pypi timed out: Connection timeout to host https://pypi.org/pypi (master.py:218)
```

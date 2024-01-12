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

## Pull the Docker Image

```bash
docker pull pypa/bandersnatch:latest
```

## Run (with docker-compose v2)

```bash
docker compose up -d
```

## Watching live logs

```bash
docker compose logs -f bandersnatch
docker compose logs -f bandersnatch_nginx
```

## Removing the Repository

To remove the Bandersnatch repository that you've set up using Docker Compose, follow these steps. Please be aware that this process will delete all the packages and configuration files you have downloaded or created. Ensure you have backups if necessary.

1. **Stop the Docker Containers**: Before removing any files, it's important to stop the running Docker containers to prevent any file corruption or data loss. Use the command:

```bash
docker compose down
```

2. **Remove the Packages and Configuration Files**: To delete all the downloaded packages and configuration files, run the following command. This will remove the `packages` and entire `config` directory directory inside your `config` folder, which contains all the mirrored Python packages.

```bash
rm -rf ./data/
rm -rf ./config/
```

3. **Clean up Docker Artifacts**: Finally, to remove any Docker volumes, networks, or other artifacts that were created with the Docker Compose file, you can use the following command:

```bash
docker system prune --volumes
```

## Caveats

Watch out for your docker MTU settings. Changing the MTU of the daemon is not going to help (see issue #1271).
Otherwise you might get error messages like these:

```bash
ERROR: Call to list_packages_with_serial @ https://pypi.org/pypi timed out: Connection timeout to host https://pypi.org/pypi (master.py:218)
```

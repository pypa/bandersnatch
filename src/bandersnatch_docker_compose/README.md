# Bandersnatch with docker compose

# Table of Contents

[Introduction](#introduction)

[Preparation](#preparation)

[Pull the Docker Image](#pull-the-docker-image)

[Run with Docker Compose](#run-with-docker-compose-v2)

[Watching Live Logs](#watching-live-logs)

[(Optional) - Enabling HTTPS Support](#optional---enabling-https-support)

[Removing the Repository](#removing-the-repository)

[Caveats](#caveats)

## Introduction

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

### (Optional) - Enabling HTTPS Support

The `bandersnatch_docker_compose` setup now includes optional HTTPS support for the Nginx server.

To enable HTTPS:

- **Uncomment the HTTPS sections**:

In `docker-compose.yml` related to SSL certificate and key volumes, as well as the exposed HTTPS port.

- **Provide SSL Certificates**:

Place your SSL certificate and key files in the `src/banderx` directory and name them `certificate.crt` and `private.key`, respectively.

- Ensure that these files are not publicly accessible.

- In case you need just a Self-Signed certificate just use the guide [here](https://github.com/pypa/bandersnatch/blob/main/src/banderx/README.md)

- **Uncomment the HTTPS sections in `nginx.conf`**:

In the `nginx.conf` file located in the `banderx` directory, uncomment the server block for HTTPS and the server block for redirecting HTTP to HTTPS.

- **Rebuild and Restart the Containers**:

After making these changes, rebuild and restart your Docker containers.

```bash
docker-compose down
docker-compose up --build -d
```

#### Integrating with Docker Compose

```yaml
services:
   bandersnatch_nginx:
      # ... other configurations ...
      volumes:
      # ... Other volunes ...
      - "../banderx/certificate.crt:/etc/ssl/certs/nginx.crt:ro" # SSL certificate
      - "../banderx/private.key:/etc/ssl/private/nginx.key:ro" # SSL key
```

#### Test HTTPS Connection

Ensure that your Nginx server is correctly serving content over HTTPS and access it using https.

##### Using a Web Browser

- Open your web browser.

- Navigate to `https://pypi-repo-domain>:44300`.

- You should see your site served over HTTPS.

> Note - Your browser may display a security warning if you are using a self-signed certificate.

##### Using `curl` Command

- Open a terminal or command prompt.

- Run the following command:

  ```bash
  curl -vk https://pypi-repo-domain:44300
  ```

  - Replace `<your-server-domain-or-IP>` with your server's domain name or IP address.

  - The `-k` option allows `curl` to perform "insecure" SSL connections and transfers, useful if you're using a self-signed certificate.

- If the Nginx server is correctly serving content over HTTPS, you should see the HTML content of your website in the terminal output.

> Note
>
> - Ensure that the port `44300` is open and accessible from your network.
>
> - If you are using a self-signed certificate, web browsers and tools like `curl` may show a warning because the certificate is not signed by a recognized Certificate Authority.
>
> - This is expected behavior for self-signed certificates. For a production environment, it's recommended to use a certificate from a recognized Certificate Authority.

## Removing the Repository

To remove the Bandersnatch repository that you've set up using Docker Compose, follow these steps. Please be aware that this process will delete all the packages and configuration files you have downloaded or created. Ensure you have backups if necessary.

- **Stop the Docker Containers**: Before removing any files, it's important to stop the running Docker containers to prevent any file corruption or data loss. Use the command:

```bash
docker compose down
```

- **Remove the Packages and Configuration Files**: To delete all the downloaded packages and configuration files, run the following command. This will remove the `packages` and entire `config` directory directory inside your `config` folder, which contains all the mirrored Python packages.

```bash
rm -rf ./data/
rm -rf ./config/
```

- **Clean up Docker Artifacts**: Finally, to remove any Docker volumes, networks, or other artifacts that were created with the Docker Compose file, you can use the following command:

```bash
docker system prune --volumes
```

## Caveats

Watch out for your docker MTU settings. Changing the MTU of the daemon is not going to help (see issue #1271).
Otherwise you might get error messages like these:

```bash
ERROR: Call to list_packages_with_serial @ https://pypi.org/pypi timed out: Connection timeout to host https://pypi.org/pypi (master.py:218)
```

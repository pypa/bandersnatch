# banderx

Simple nginx PEP 501 + 691 mirror filesystem serving example.

- You will need to attach the bandersantch file system via a bind mount or some other means.

## Build

- `docker build --tag banderx src/banderx`

## Run

- `docker run --detach --name banderx banderx`

## (Optional) - Generate a Self-Signed Certificate for Bandersnatch

> Note - Use this only for HTTPS support

- **Generate a 2048-bit RSA Private Key**:

  This key is used to decrypt traffic. Run the following command in PowerShell or Command Prompt (on Windows):

  ```bash
  openssl genrsa -out ./src/banderx/private.key 2048
  ```

  This will create a private key file `key.key`.

- **Generate a Certificate S igning Request (CSR)**:

  Using the private key from the previous step, generate a CSR:

  ```bash
  openssl req -new -key ./src/banderx/private.key -out ./src/banderx/certificate.csr
  ```

  You will be prompted to enter details for the certificate; you can fill these out as needed or leave them blank.

- **Self-Sign the Certificate**:

  Sign the CSR with the private key, setting the certificate's validity period. For example, for a validity of 365 days:

  ```bash
  openssl x509 -req -days 180 -in ./src/banderx/certificate.csr -signkey ./src/banderx/private.key -out ../banderx/certificate.crt
  ```

  This creates a self-signed certificate `cert.crt` in the `banderx` directory.

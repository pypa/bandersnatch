# banderx

Simple nginx PEP 501 + 691 mirror filesystem serving example.

- You will need to attach the bandersantch file system via a bind mount or some other means.

## Build

- `docker build --tag banderx src/banderx`

## Run

- `docker run --detach --name banderx banderx`

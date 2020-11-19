FROM python:3 as base

FROM base as builder
RUN mkdir /install
WORKDIR /install
ADD requirements_swift.txt /install
ADD requirements.txt /install
RUN pip install --target="/install" --upgrade pip setuptools wheel
RUN pip install --target="/install" \
    -r requirements.txt \
    -r requirements_swift.txt


FROM python:3-slim

COPY --from=builder /install /usr/local/lib/python3.9/site-packages

RUN mkdir /bandersnatch && mkdir /conf && chmod 777 /conf
WORKDIR /bandersnatch
COPY setup.cfg /bandersnatch
COPY setup.py /bandersnatch
COPY README.md /bandersnatch
COPY LICENSE /bandersnatch

COPY src /bandersnatch/src
RUN pip --no-cache-dir install /bandersnatch/[swift]

CMD ["python", "/bandersnatch/src/runner.py", "3600"]

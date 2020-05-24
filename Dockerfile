FROM python:3

RUN mkdir /bandersnatch
RUN mkdir /conf && chmod 777 /conf
ADD setup.cfg /bandersnatch
ADD setup.py /bandersnatch
ADD requirements.txt /bandersnatch
ADD requirements_swift.txt /bandersnatch
ADD README.md /bandersnatch
ADD CHANGES.md /bandersnatch
COPY src /bandersnatch/src

# OPTIONAL: Include a config file
# Remember to bind mount the "directory" in bandersnatch.conf
# Reccomended to bind mount /conf - `runner.py` defaults to look for /conf/bandersnatch.conf
# ADD bandersnatch.conf /etc

RUN pip --no-cache-dir install --upgrade pip setuptools wheel
RUN pip --no-cache-dir install --upgrade -r /bandersnatch/requirements.txt -r /bandersnatch/requirements_swift.txt
RUN pip --no-cache-dir -v install /bandersnatch/[swift]

CMD ["python", "/bandersnatch/src/runner.py", "3600"]

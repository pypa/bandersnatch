FROM python:3

RUN mkdir -p /src
ADD setup.py /src
ADD requirements.txt /src
ADD README.md /src
ADD CHANGES.md /src
ADD src /src/src

# OPTIONAL: Include a config file
# Remember to bind mount the "directory" in bandersnatch.conf
# Reccomended to bind mount /conf - `runner.py` defaults to look for /conf/bandersnatch.conf
# ADD bandersnatch.conf /etc

RUN pip install --upgrade pip
RUN pip install --upgrade -r /src/requirements.txt
RUN cd /src && pip install .

CMD ["python", "/src/src/runner.py", "3600"]

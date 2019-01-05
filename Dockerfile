FROM python:3

RUN mkdir -p /src
ADD setup.py /src
ADD requirements.txt /src
ADD README.md /src
ADD CHANGES.md /src
ADD src /src/src

# Remember to bind mount the "directory" in bandersnatch.conf
# Could also comment this out and bind mount in the config and add arg below
ADD bandersnatch.conf /etc

RUN pip install --upgrade pip
RUN pip install --upgrade -r /src/requirements.txt
RUN cd /src && pip install .

# Please adjust the interval - Could move this to the config file or ENV Variable
CMD ["python", "/src/src/runner.py", "3600"]

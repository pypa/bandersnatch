#!/bin/bash

if [ ! -e bin/python3 ]; then
    virtualenv --python=python3.6 .
fi
if [ ! -e bin/buildout ]; then
    bin/pip install zc.buildout
    bin/pip install virtualenv
fi
bin/pip install --upgrade zc.buildout==2.11.1
bin/pip install --upgrade setuptools==38.5.2
bin/pip install --upgrade virtualenv==15.1.0
bin/buildout

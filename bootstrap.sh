#!/bin/bash

if [ ! -e bin/python3.5 ]; then
    virtualenv --python=python3.5 .
fi
if [ ! -e bin/buildout ]; then
    bin/pip install zc.buildout
    bin/pip install virtualenv
fi
bin/buildout

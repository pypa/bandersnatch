#!/bin/bash

if [ ! -e bin/python2.7 ]; then
    virtualenv .
fi
bin/pip install --upgrade zc.buildout==2.5.3
bin/pip install --upgrade setuptools==33.1.1
bin/pip install --upgrade virtualenv==15.1.0
bin/buildout

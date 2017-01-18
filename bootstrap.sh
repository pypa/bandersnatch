#!/bin/bash

if [ ! -e bin/python2.7 ]; then
    virtualenv .
    bin/pip install zc.buildout
    bin/pip install virtualenv
fi
bin/buildout

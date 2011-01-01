#!/usr/bin/env python
# replace this with actual mirror location, 
# or set PYPITARGET environment variable
targetdir = '/pypi'

import os, sys, signal

dirname = os.path.dirname(sys.argv[0])

if "PYPITARGET" in os.environ:
    targetdir = os.environ["PYPITARGET"]

if not os.path.exists(targetdir):
    print "Status: 412 Precondition failed"
    print "Content-type: text/plain"
    print
    print "PyPI mirror targetdir not configured"
    raise SystemExit

# detach from webserver
if os.fork() == 0:
    # child process: run mirroring quietly
    # close fds so that the web server won't wait for further input
    os.close(0)
    os.close(1)
    os.close(2)
    os.execl(os.path.join(dirname, "pep381run"),
             os.path.join(dirname, "pep381run"),
             "-q", targetdir)
else:
    # parent process; print status and exit
    print "Content-Type: text/plain"
    print
    print "Mirroring started"

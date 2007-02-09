#!/usr/bin/env python
#
##
# Copyright (c) 2006-2007 Apple Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# DRI: Cyrus Daboo, cdaboo@apple.com
##
#
# Generates fs_usage counts for CalDAVTester script runs.
#

import subprocess

from src.manager import manager
import getopt
import os
import signal
import sys

def usage():
    print """Usage: fsusage [options]
Options:
    -h       Print this help and exit
    -f file  pid file of caldavd server
"""

def getFSUsage(testscript, runs, pid):
    fd = open("temp", "w")
    cid = subprocess.Popen(["fs_usage", "-f", "filesys", "%s" %(pid,),], stdout=fd).pid
    
    sname = "scripts/server/serverinfo.xml"
    pname = None
    fnames = [testscript]

    mgr = manager(level=manager.LOG_NONE)
    result, timing = mgr.runWithOptions(sname, pname, fnames, {})

    os.kill(cid, signal.SIGTERM)

    fd = open("temp", "r")
    ctr = 0
    for line in fd:
        ctr += 1

    return ctr / runs

if __name__ == "__main__":

    options, args = getopt.getopt(sys.argv[1:], "f:")

    for option, value in options:
        if option == "-h":
            usage()
            sys.exit(0)
        elif option == "-f":
            pidfile = value
        else:
            print "Unrecognized option: %s" % (option,)
            usage()
            raise ValueError

    # First try to get pid of caldavd process
    fd = open(pidfile, "r")
    s = fd.read()
    pid = int(s)
    fd = None
    
    tests = (
        ("performance/get/get-small.xml", 10, "GET small",),
        ("performance/get/get-large.xml", 10, "GET large",),
        ("performance/put/put-small.xml", 10, "PUT small",),
        ("performance/put/put-large.xml", 10, "PUT large",),
        ("performance/propfind/propfind-small.xml", 10, "PROPFIND small",),
        ("performance/propfind/propfind-medium.xml", 10, "PROPFIND medium",),
        ("performance/propfind/propfind-large.xml", 10, "PROPFIND large",),
    )
    
    result = []
    for test in tests:
        print "%s\t%s" % (test[2], getFSUsage(test[0], test[1], pid),)

##
# Copyright (c) 2006-2010 Apple Inc. All rights reserved.
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
##

"""
Class to manage the testing process.
"""

from src.populate import populate
from src.serverinfo import serverinfo
from xml.etree.ElementTree import ElementTree
from xml.parsers.expat import ExpatError
import getopt
import httplib
import os
import random
import src.xmlDefs
import sys
import time

# Exceptions

EX_INVALID_CONFIG_FILE = "Invalid Config File"
EX_FAILED_REQUEST = "HTTP Request Failed"

class manager(object):

    """
    Main class that runs test suites defined in an XML config file.
    """

    LOG_NONE    = 0
    LOG_ERROR   = 1
    LOG_LOW     = 2
    LOG_MEDIUM  = 3
    LOG_HIGH    = 4

    def __init__( self, text=True, level=LOG_HIGH, log_file=None ):
        self.server_info = serverinfo()
        self.populator = None
        self.depopulate = False
        self.tests = []
        self.textMode = text
        self.pid = 0
        self.memUsage = None
        self.logLevel = level
        self.logFile = log_file
        self.digestCache = {}
    
    def log(self, level, str, indent = 0, indentStr = " ", after = 1, before = 0):
        if self.textMode and level <= self.logLevel:
            if before:
                self.logit("\n" * before)
            if indent:
                self.logit(indentStr * indent)
            self.logit(str)
            if after:
                self.logit("\n" * after)

    def logit(self, str):
        if self.logFile:
            self.logFile.write(str)
        else:
            print str,

    def readXML( self, serverfile, populatorfile, testfiles, all, moresubs = {} ):

        self.log(manager.LOG_HIGH, "Reading Server Info from \"%s\"" % serverfile, after=2)
    
        # Open and parse the server config file
        try:
            tree = ElementTree(file=serverfile)
        except ExpatError, e:
            raise RuntimeError("Unable to parse file '%s' because: %s" % (serverfile, e,))

        # Verify that top-level element is correct
        serverinfo_node = tree.getroot()
        if serverinfo_node.tag != src.xmlDefs.ELEMENT_SERVERINFO:
            raise EX_INVALID_CONFIG_FILE
        if not len(serverinfo_node):
            raise EX_INVALID_CONFIG_FILE
        self.server_info.parseXML(serverinfo_node)
        self.server_info.addsubs(moresubs)
        
        # Open and parse the populator config file
        if populatorfile:
            self.log(manager.LOG_HIGH, "Reading Populator Info from \"%s\"" % populatorfile, after=2)
    
            try:
                tree = ElementTree(file=populatorfile)
            except ExpatError, e:
                raise RuntimeError("Unable to parse file '%s' because: %s" % (populatorfile, e,))

            # Verify that top-level element is correct
            populate_node = tree.getroot()
            if populate_node.tag != src.xmlDefs.ELEMENT_POPULATE:
                raise EX_INVALID_CONFIG_FILE
            if not len(populate_node):
                raise EX_INVALID_CONFIG_FILE
            self.populator = populate(self)
            self.populator.parseXML(populate_node)

        for testfile in testfiles:
            # Open and parse the config file
            try:
                tree = ElementTree(file=testfile)
            except ExpatError, e:
                raise RuntimeError("Unable to parse file '%s' because: %s" % (testfile, e,))
            
            # Verify that top-level element is correct
            from src.caldavtest import caldavtest
            caldavtest_node = tree.getroot()
            if caldavtest_node.tag != src.xmlDefs.ELEMENT_CALDAVTEST:
                self.log(manager.LOG_HIGH, "Ignoring file \"%s\" because it is not a test file" % (testfile,), after=2)
                continue
            if not len(caldavtest_node):
                raise EX_INVALID_CONFIG_FILE
            self.log(manager.LOG_HIGH, "Reading Test Details from \"%s\"" % testfile, after=2)
                
            # parse all the config data
            test = caldavtest(self, testfile)
            test.parseXML(caldavtest_node)
            
            # ignore if all mode and ignore-all is set
            if not all or not test.ignore_all:
                self.tests.append(test)

    def readCommandLine(self):
        sname = "scripts/server/serverinfo.xml"
        pname = None
        dname = "scripts/tests"
        fnames = []
        all = False
        excludes = set()
        subdir = None
        pidfile = "../CalendarServer/logs/caldavd.pid"
        random_order = False
        options, args = getopt.getopt(sys.argv[1:], "s:p:dmx:", ["all", "subdir=", "exclude=", "pid=", "random"])
        
        # Process single options
        for option, value in options:
            if option == "-s":
                sname = value
            elif option == "-p":
                pname = value
            elif option == "-d":
                self.depopulate = True
            elif option == "-x":
                dname = value
            elif option == "--all":
                all = True
            elif option == "--subdir":
                subdir = value + "/"
            elif option == "--exclude":
                excludes.add(value)
            elif option == "-m":
                self.memUsage = True
            elif option == "--pid":
                pidfile = value
            elif option == "--random":
                random_order = True
                
        if all:
            files = []
            os.path.walk(dname, lambda arg,dir,names:files.extend([os.path.join(dir, name) for name in names]), None)
            for file in files:
                if file.endswith(".xml") and file[len(dname)+1:] not in excludes:
                    if subdir is None or file[len(dname)+1:].startswith(subdir):
                        fnames.append(file)

        # Remove any server info file from files enumerated by --all
        fnames[:] = [x for x in fnames if (x != sname) and (not pname or (x != pname))]

        # Process any file arguments as test configs
        for f in args:
            if f[0] != '/':
                f = os.path.join(dname, f)
            fnames.append(f)
        
        # Randomize file list
        if random_order:
            new_fnames = []
            while fnames:
                element = random.choice(fnames)
                new_fnames.append(element)
                fnames.remove(element)
            fnames = new_fnames

        self.readXML(sname, pname, fnames, all)
            
        if self.memUsage:
            fd = open(pidfile, "r")
            s = fd.read()
            self.pid = int(s)

    def runWithOptions(self, sname, pname, fnames, moresubs, pid=0, memUsage=False, all = False, depopulate = False):
        self.depopulate = depopulate
        self.readXML(sname, pname, fnames, all, moresubs)
        self.pid = pid
        self.memUsage = memUsage
        return self.runAll()

    def runAll(self):
        
        if self.populator:
            self.runPopulate();

        startTime = time.time()
        ok = 0
        failed = 0
        ignored = 0
        try:
            for test in self.tests:
                o, f, i = test.run()
                ok += o
                failed += f
                ignored += i
        except:
            failed += 1
            import traceback
            traceback.print_exc()

        endTime = time.time()

        if self.populator and self.depopulate:
            self.runDepopulate()

        self.log(manager.LOG_LOW, "Overall Results: %d PASSED, %d FAILED, %d IGNORED" % (ok, failed, ignored), before=2, indent=4)
        self.log(manager.LOG_LOW, "Total time: %.3f secs" % (endTime- startTime,))

        return failed, endTime - startTime

    def runPopulate(self):
        self.populator.generateAccounts()
    
    def runDepopulate(self):
        self.populator.removeAccounts()

    def httpRequest(self, method, uri, headers, data):

        # Do the http request
        http = httplib.HTTPConnection( self.server_info.host, self.server_info.port )
        try:
            http.request( method, uri, data, headers )
        
            response = http.getresponse()
        
            respdata = response.read()

        finally:
            http.close()
        
        return response.status, respdata
        
    def getMemusage(self):
        """
        
        @param pid: numeric pid of process to get memory usage for
        @type pid:  int
        @retrun:    tuple of (RSS, VSZ) values for the process
        """
        
        fd = os.popen("ps -l -p %d" % (self.pid,))
        data = fd.read()
        lines = data.split("\n")
        procdata = lines[1].split()
        return int(procdata[6]), int(procdata[7])


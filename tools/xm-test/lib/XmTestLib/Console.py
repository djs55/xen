#!/usr/bin/python
"""
 XmConsole.py - Interact with a xen console, getting return codes and
                output from commands executed there.

 Copyright (C) International Business Machines Corp., 2005
 Author: Dan Smith <danms@us.ibm.com>

 This program is free software; you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation; under version 2 of the License.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program; if not, write to the Free Software
 Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

 NB: This requires the domU's prompt to be set to
     a _very_ specific value, set in the PROMPT
     variable of this script
"""
import sys
import os
import pty
import tty
import termios
import fcntl
import select

from Test import *

TIMEDOUT = 1
RUNAWAY  = 2

class ConsoleError(Exception):
    def __init__(self, msg, reason=TIMEDOUT):
        self.errMsg = msg
        self.reason = reason

    def __str__(self):
        return str(self.errMsg)

class XmConsole:

    def __init__(self, domain, historyLimit=256, historySaveAll=True, historySaveCmds=False, cLimit=131072):
        """
        Parameters:
          historyLimit:     specifies how many lines of history are maintained
          historySaveAll:   determines whether or not extra messages in
                            between commands are saved
          historySaveCmds : determines whether or not the command echos
                            are included in the history buffer
        """

        self.TIMEOUT          = 30
        self.PROMPT           = "@%@%> "
        self.domain           = domain
        self.historyBuffer    = []
        self.historyLines     = 0
        self.historyLimit     = historyLimit
        self.historySaveAll   = historySaveAll
        self.historySaveCmds  = historySaveCmds
        self.debugMe          = False
        self.limit            = cLimit

        consoleCmd = ["/usr/sbin/xm", "xm", "console", domain]

        if verbose:
            print "Console executing: %s" % str(consoleCmd)

        pid, fd = pty.fork()

        if pid == 0:
            os.execvp("/usr/sbin/xm", consoleCmd[1:])

        self.consolePid = pid
        self.consoleFd  = fd

        tty.setraw(self.consoleFd, termios.TCSANOW)

        self.__chewall(self.consoleFd)


    def __addToHistory(self, line):
        self.historyBuffer.append(line)
        self.historyLines += 1
        if self.historyLines > self.historyLimit:
            self.historyBuffer = self.historyBuffer[1:]
            self.historyLines -= 1


    def clearHistory(self):
        """Clear the history buffer"""
        self.historyBuffer = []
        self.historyLines = 0


    def getHistory(self):
        """Returns a string containing the entire history buffer"""
        output = ""

        for line in self.historyBuffer:
            output += line + "\n"

        return output


    def setTimeout(self, timeout):
        """Sets the timeout used to determine if a remote command
        has blocked"""
        self.TIMEOUT = timeout


    def setPrompt(self, prompt):
        """Sets the string key used to delimit the end of command
        output"""
        self.PROMPT = prompt


    def __chewall(self, fd):
        timeout = 0
        bytes   = 0
        
        while timeout < 3:
            i, o, e = select.select([fd], [], [], 1)
            if fd in i:
                try:
                    foo = os.read(fd, 1)
                    if self.debugMe:
                        sys.stdout.write(foo)
                    bytes += 1
                except Exception, exn:
                    raise ConsoleError(str(exn))

            else:
                timeout += 1

            if self.limit and bytes >= self.limit:
                raise ConsoleError("Console run-away (exceeded %i bytes)"
                                   % self.limit, RUNAWAY)

        if self.debugMe:
            print "Ignored %i bytes of miscellaneous console output" % bytes
        
        return bytes


    def __runCmd(self, command, saveHistory=True):
        output = ""
        line   = ""
        lines  = 0
        bytes  = 0

        self.__chewall(self.consoleFd)

        if verbose:
            print "[%s] Sending `%s'" % (self.domain, command)

        os.write(self.consoleFd, "%s\n" % command)

        while True:
            i, o, e = select.select([self.consoleFd], [], [], self.TIMEOUT)

            if self.consoleFd in i:
                try:
                    str = os.read(self.consoleFd, 1)
                    if self.debugMe:
                        sys.stdout.write(str)
                    bytes += 1
                except Exception, exn:
                    raise ConsoleError(
                        "Failed to read from console (fd=%i): %s" %
                        (self.consoleFd, exn))
            else:
                raise ConsoleError("Timed out waiting for console")

            if self.limit and bytes >= self.limit:
                raise ConsoleError("Console run-away (exceeded %i bytes)"
                                   % self.limit, RUNAWAY)

            if str == "\n":
                if lines > 0:
                    output += line + "\n"
                    if saveHistory:
                        self.__addToHistory(line)
                elif self.historySaveCmds and saveHistory:
                    self.__addToHistory("*" + line)
                lines += 1
                line = ""
            elif str == "\r":
                pass # ignore \r's
            else:
                line += str

            if line == self.PROMPT:
                break

        return output


    def runCmd(self, command):
        """Runs a command on the remote terminal and returns the output
        as well as the return code.  For example:
        
        ret = c.runCmd("ls")
        print ret["output"]
        sys.exit(run["return"])
        
        """

        # Allow exceptions to bubble up
        realOutput = self.__runCmd(command)
        retOutput  = self.__runCmd("echo $?", saveHistory=False)

        try:
            retCode =  int(retOutput)
        except:
            retCode = 255
        return {
            "output": realOutput,
            "return": retCode,
            }

    def sendInput(self, input):
        """Sends input to the remote terminal, but doesn't check
        for a return code"""
        realOutput = self.__runCmd(input)
        return {
            "output": realOutput,
            "return": 0,
            }

    def closeConsole(self):
        """Closes the console connection and ensures that the console
        process is killed"""
        os.close(self.consoleFd)
        os.kill(self.consolePid, 2)


    def setLimit(self, limit):
        """Sets a limit on the number of bytes that can be
        read in an attempt to run a command.  We need this when
        running something that can run away"""
        try:
            self.limit = int(limit)
        except Exception, e:
            self.limit = None
            
                   
if __name__ == "__main__":
    """This is both an example of using the XmConsole class, as
    well as a utility for command-line execution of single commands
    on a domU console.  Prints output to stdout.  Exits with the same
    code as the domU command.
    """

    verbose = True
    
    try:
        t = XmConsole(sys.argv[1])
    except ConsoleError, e:
        print "Failed to attach to console (%s)" % str(e)
        sys.exit(255)

    try:
        run = t.runCmd(sys.argv[2])
    except ConsoleError, e:
        print "Console failed (%)" % str(e)
        sys.exit(255)
        
    t.closeConsole()
    
    print run["output"],
    sys.exit(run["return"])
    
        

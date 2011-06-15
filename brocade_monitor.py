#!/usr/bin/env python
###################################################################################################
# Script to monitor the throughput and errors on brocade FABOS interfaces
###################################################################################################
# NOTE - Stats are cleared on each iteration of the script
#      - Requires pexpect module to be installed http://www.noah.org/wiki/pexpect
#
# Usage - Script has been designed to be used as a scripted input for Splunk http://www.splunk.com
#
# The main part of this script was provided by Noah Spurrier who created the fantastic pexpect @
# http://pexpect.sourceforge.net/
#
# Most was taken from the monitor.py in the examples directory
###################################################################################################

""" This runs a sequence of commands on a remote host using SSH. It runs a
simple system checks such as uptime and free to monitor the state of the remote
host.

./monitor.py [-s brocade_switch] [-u username] [-p password]
    -s : hostname of the remote switch to login to.
    -u : username to user for login.
    -p : Password to user for login.

Example:
    This will print information about the given host:
        ./brocade_monitor.py -s brocade_switch -u mylogin -p mypassword

It works like this:
    Login via SSH (This is the hardest part).
    Run and parse 'switchshow'.
    Run 'switchportstats' on each "Online" port
    Exit the remote host.
"""

import os, sys, time, re, getopt, getpass
import traceback
import pexpect

#
# Some constants.
#
COMMAND_PROMPT = ':admin> ' ### This is way too simple for industrial use -- we will change is ASAP.
TERMINAL_PROMPT = '(?i)terminal type\?'
TERMINAL_TYPE = 'vt100'
# This is the prompt we get if SSH does not have the remote host's public key stored in the cache.
SSH_NEWKEY = '(?i)are you sure you want to continue connecting'

def exit_with_usage():

    print globals()['__doc__']
    os._exit(1)

def main():

    global COMMAND_PROMPT, TERMINAL_PROMPT, TERMINAL_TYPE, SSH_NEWKEY
    ######################################################################
    ## Parse the options, arguments, get ready, etc.
    ######################################################################
    try:
        optlist, args = getopt.getopt(sys.argv[1:], 'h?s:u:p:', ['help','h','?'])
    except Exception, e:
        print str(e)
        exit_with_usage()
    options = dict(optlist)
    if len(args) > 1:
        exit_with_usage()

    if [elem for elem in options if elem in ['-h','--h','-?','--?','--help']]:
        print "Help:"
        exit_with_usage()

    if '-s' in options:
        host = options['-s']
    else:
        host = raw_input('hostname: ')
    if '-u' in options:
        user = options['-u']
    else:
        user = raw_input('username: ')
    if '-p' in options:
        password = options['-p']
    else:
        password = getpass.getpass('password: ')

    #
    # Login via SSH
    #
    child = pexpect.spawn('ssh -l %s %s'%(user, host))
    i = child.expect([pexpect.TIMEOUT, SSH_NEWKEY, COMMAND_PROMPT, '(?i)password'])
    if i == 0: # Timeout
        print 'ERROR! could not login with SSH. Here is what SSH said:'
        print child.before, child.after
        print str(child)
        sys.exit (1)
    if i == 1: # In this case SSH does not have the public key cached.
        child.sendline ('yes')
        child.expect ('(?i)password')
    if i == 2:
        # This may happen if a public key was setup to automatically login.
        # But beware, the COMMAND_PROMPT at this point is very trivial and
        # could be fooled by some output in the MOTD or login message.
        pass
    if i == 3:
        child.sendline(password)
        # Now we are either at the command prompt or
        # the login process is asking for our terminal type.
        i = child.expect ([COMMAND_PROMPT, TERMINAL_PROMPT])
        if i == 1:
            child.sendline (TERMINAL_TYPE)
            child.expect (COMMAND_PROMPT)

    # Now we should be at the command prompt and ready to run some commands.
    output_file = open('output.log', 'w')

    # Run switchshow.
    child.sendline ('switchshow') # Run switchshow to pull in port data
    child.expect (COMMAND_PROMPT)
    switchshow_output = child.before
    online_ports_list = re.findall(r"\s+(\d+)\s+\d+\s+\w+\s+\w+\s+Online", switchshow_output ) # Extract only Online ports
    child.sendline ('portstats64show 0') # Extract the metric headers from port 0 which should always be present
    child.expect (COMMAND_PROMPT)
    portstatsshow_zero_output = child.before
    portstatsshow_headers = re.findall(r"stat64_rate(\w+)\s+\d+\s+", portstatsshow_zero_output) # Read in the metric headers
    fw = 14
    output_file.write("port".center(fw) + ''.join([s.center(fw) for s in (portstatsshow_headers)])) # Format output and write to file
    output_file.write('\n') # Move to new line

    # Go through collecting stats for each port
    for port in online_ports_list:
        child.sendline ('portstats64show ' + port) # For each online port get metric values
        child.expect (COMMAND_PROMPT)
        portstatsshow_output = child.before
        portstatsshow_formated = re.findall(r"stat64_rate\w+\s+(\d+)\s+", portstatsshow_output) # Read in the metric values
        line = []
        for i in range(len(portstatsshow_headers)):
            line.append(portstatsshow_formated[i])
        output_file.write(port.center(fw) + ''.join([str(s).center(fw) for s in line])) # For each port append metrics
        output_file.write('\n') # Move to new line
        #child.sendline ('portstatsclear ' + port) # Clear port metrics for next run
        #child.expect (COMMAND_PROMPT)
    output_file.write('\n') # Move to new line
    output_file.write('\n') # Move to new line
    output_file.close # Close off output file
    output_file = open('output.log', 'r')
    print output_file.read()
    output_file.close # Close off output file

    # Now exit the remote host.
    child.sendline ('exit')
    index = child.expect([pexpect.EOF, "(?i)there are stopped jobs"])
    if index==1:
        child.sendline("exit")
        child.expect(EOF)

if __name__ == "__main__":

    try:
        main()
    except Exception, e:
        print str(e)
        traceback.print_exc()
        os._exit(1)

#!/usr/bin/env python

import os, sys, time, gzip, string, tempfile, shlex, subprocess, thread, syslog
from pexpect import *

files = ["MetaData", "postgres", "ptsweb", "faultdbtst01", "faultdbfiweekly", "faultdbfitst01", "faultdbfisim04", "faultdbfisim03", "faultdbfisim02", "faultdbfisim01", "faultdbfirelease", "faultdbfiqa", "checksysreportdb"]

date = time.strftime("%d-%m-%y")

global thread_finished_count
thread_finished_count = 0
no_of_files = 13

def inc_thread_finished_count():
    global thread_finished_count
    thread_finished_count += 1

def threaded_scp(user, server, path_to_target_file, path_to_destination ):
    logger("Retrieving - %s" % (path_to_target_file))
    command = 'scp %s@%s:%s %s' % (user, server, path_to_target_file, path_to_destination)
    (command_output, exitstatus) = run(command, withexitstatus=1, timeout=None)
    if exitstatus == 0:
       logger("Successful, attempting gunzip - %s" % (path_to_target_file))
       threaded_gunzip("test", path_to_target_file)
       inc_thread_finished_count()
    else:
       return exitstatus

def threaded_gunzip(test, file):
    logger("Gunzipping - %s" % (file))
    write_file = string.rstrip(file, '.gz')
    subprocess.Popen([r"gunzip","%s" % (file)]).wait()
    logger("Gunzipping Successful - %s" % (write_file))
    threaded_postgres_import(write_file)

def threaded_postgres_import(file):
    file_name = os.path.split(file)[-1]
    database_name_split = file_name.split( "_" )
    database_name =  database_name_split[0]
    logger("Importing data to - %s " % (database_name ))
    if database_name == "MetaData":
        postgres_command = "/usr/bin/psql -f %s" % (file)
    else:
        postgres_command = "/usr/bin/psql -d %s -f %s" % (database_name, file)
    postgres_args = shlex.split(postgres_command)
    data_import_log = "%s.log" % (file)
    p = subprocess.Popen(postgres_args,stderr=subprocess.STDOUT, stdout=subprocess.PIPE).communicate()[0]
    logfile = open(data_import_log, 'w')
    logfile.write(p)
    logfile.close()
    os.remove(file)
    logger("Importing data Successful - see %s for details" % (data_import_log))

def run_postgres_file(file):
    logger("Running postgres commands from  - %s " % (file))
    postgres_command = "/usr/bin/psql -f %s" % (file)
    postgres_args = shlex.split(postgres_command)
    data_import_log = "/stage/backup/pgsql/drop_create_commands.log"
    p = subprocess.Popen(postgres_args,stderr=subprocess.STDOUT, stdout=subprocess.PIPE).communicate()[0]
    logfile = open(data_import_log, 'w')
    logfile.write(p)
    logfile.close()
    logger("Commands Successful - see %s for details" % (data_import_log ))

def restart_postgres(test):
    logger("Restart postgres to avoid any locking")
    restart_command = ["/usr/bin/sudo", "/sbin/service", "postgresql", "restart"]
    output = subprocess.Popen(restart_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0]

def logger(message):
    syslog.syslog(message)

if __name__ == "__main__":

   try:
      logger("import_databases.py started")
      #Restart posgres to clear any locks
      restart_postgres("test")
      #Give it a chance to come back up
      time.sleep(5)

      #Drop/Create databases
      run_postgres_file("/app_scripts/drop_create_commands")

      for file in files:
         if file == "MetaData":
             file_dated = "/stage/backup/pgsql/%s__%s.gz" % (file, date)
         else:
             file_dated = "/stage/backup/pgsql/%s_%s.gz" % (file, date)
         thread.start_new_thread(threaded_scp, ("postgres", "masoradev05", file_dated, "/stage/backup/pgsql/"))
   except:
      print "Error: unable to start thread"
      logger("Error: unable to start thread")

   while thread_finished_count < no_of_files:
      time.sleep(2)

   logger("import_databases.py finished")
   os._exit(0)
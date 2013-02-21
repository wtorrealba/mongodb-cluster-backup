#!/usr/bin/env python
import optparse
from pymongo import MongoClient
from fabric.api import run, settings, execute, task, env
import datetime 


# =================================================================================================
# Function that create the connection to the mongos server to be use as primary 
# source of information in order to pick the servers that will be stoppped for 
# mongodump purpose
#
def connect_server(host, port, user, password, verbose=False):
	try:
		if user!="":
			auth = "mongodb://" + user + ":" + password + "@"
		else:
			auth=""
		connection = MongoClient(auth+host,port)
		if verbose:
			print "Connected to ", host, " on port ",port, "..."

	except Exception, e:
		print "Oops!  There was an error.  Try again..."
		print  e
		#raise e
	return connection

# =================================================================================================
# Function that looks for the shards settings
#
def getShards(conn):
	try:
		db = conn.config
		collection = db.shards
		shards = collection.find()
		return shards
	except Exception, e:
		print "\tOops!  There was an error.  Try again..."
		print "\t",e


# =================================================================================================
# From a replica set hosts list return the first secondary detected
#
def getSecondary(hosts_list, user, password):
	for h in hosts_list.split(","):
		host_info = h.split(":")
		c = connect_server(host_info[0],int(host_info[1]),user,password)
		if not c.is_primary:
			return host_info[0]
	return ""

# =================================================================================================
# Execution of the required steps in the secondaries
#
def backup_server(prefix,data,out,directorydb):
	print "\tStarting backup for ",env.host
	
	mongodb_service = run('ls -t /etc/init.d/mongo* | awk \'{print $1;exit}\'',True)

	if not data[-1]=='/':
		data = data+'/'
	if not out[-1]=='/':
		out = out+'/'
	modifiers = ''
	if directorydb:
		modifiers = modifiers+' --directoryperdb '
	
	run('sudo '+mongodb_service+' stop')
	run('sudo mkdir '+out+prefix)
	run('sudo mongodump --journal --dbpath '+data+' --out '+out+prefix+'/'+modifiers)
	run('sudo tar -cvf '+out+env.host+'.'+prefix+'.tar '+out+prefix+'/ ')
	run('sudo rm -rf '+out+prefix+'/')
	run('sudo gzip '+out+env.host+'.'+prefix+'.tar')
	run('sudo '+mongodb_service+' start')

	print "\tBackup for ",env.host," finished"


# =================================================================================================
# Set the environment to call fabric task that makes the backup in each server 
#
def backup_servers(hosts_to_backup, prefix_backup, userssh, keyssh, dbpath, outpath, directoryperdb):
	with settings(parallel=True, user=userssh,key_filename=keyssh):
		execute(backup_server,hosts=hosts_to_backup,prefix=prefix_backup,data=dbpath,out=outpath,directorydb=directoryperdb)


# =================================================================================================
# use a connection to a mongos in order to stop the balancer and wait for any pending migration in 
# progress
#
def stopBalancer(conn):
	print ""
	print "\tStopping balancer"
	db = conn.config
	db.settings.update( { "_id": "balancer" }, { "$set": { "stopped": True } } );
	balancer_info = db.locks.find_one({"_id": "balancer"})
	while int(str(balancer_info["state"]))>0:
		print "\t\twaiting for migration"
		balancer_info = db.locks.find_one({"_id": "balancer"})
	print "\tBalancer stoppped"
	print ""


# =================================================================================================
# use a connection to a mongos in order to start the balancer
#
def startBalancer(conn):
	print ""
	print "\tStarting balancer"
	db = conn.config
	db.settings.update( { "_id": "balancer" }, { "$set": { "stopped": False } } );

	print "\tBalancer started"
	print ""
	
	
# =================================================================================================
# =================================================================================================
def main():
	# 
	# Getting the parameters for the mongos connection.
	#
	p = optparse.OptionParser()
	p.add_option('--server', '-s', default="localhost", help="mongos server that will be use as source of config." )
	p.add_option('--port', '-l', default=27017, help="port where the mongos server is listening." )
	p.add_option('--user', '-u', default="", help="user for establish the connection if mongo has authentication enabled." )
	p.add_option('--password', '-p', default="", help="password for the user to establish the connection." )
	p.add_option('--userssh', '-a', default="", help="user that will be use to establish the ssh connection to the secondaries. this user should be able to do SUDO" )
	p.add_option('--keyssh', '-k', default="", help="ssh private key to be use in the ssh connection." )
	p.add_option('--nostop', '-f', action="store_true", default=False, help="this says if the balancer should not be stopped, if this parameter is given the tool assumes that the balancer is stopped." )
	p.add_option('--nostart', '-g', action="store_true", default=False, help="this says if the balancer should not be started." )
	p.add_option('--dbpath', '-d', default="", help="location of the data into the secondaries (mongod data path)." )
	p.add_option('--outpath', '-o', default="", help="location where the backup will be stored, a folder will be created inside this path for current backup." )
	p.add_option('--directoryperdb', '-r', action="store_true", default=False, help="if this option is present indicates that the mongo data nodes are using the --directoryperdb option." )
	


	options, arguments = p.parse_args()
	if options.userssh=="" or options.keyssh=="" or options.dbpath=="" or options.outpath=="":
		print "Oops!  There was an error, check the ssh parameters and then try again..."
		print "try using the -h option."
		exit()

	#
	# Creating connection to mongos server
	#
	print "Connecting to mongos server ",options.server
	connection = connect_server(options.server, options.port, options.user, options.password, True)
	print ""


	#
	# Getting sharding information
	#
	print "Getting sharding configuration"
	shards = getShards(connection)
	print ""


	#
	# Getting the secondaries list
	#
	hosts_to_backup = []
	for s in shards:
		hosts = str(s["host"])
		hosts = hosts.replace(str(s["_id"]),"").strip()
		hosts = hosts.replace("/","").strip()
		print "Getting secondary from hosts in ",hosts
		h = getSecondary(hosts,options.user, options.password)
		hosts_to_backup.append(h)
		#print h

	print ""
	print "Secondaries to be stopped"
	print "\t",hosts_to_backup
	print ""

	#
	# Creating prefix to identify the backup to be build.
	#
	today = datetime.datetime.now()
	prefix_backup = str(today.strftime("%Y%m%d%H%M%S"))
	

	#
	# Backing up servers.
	#
	print "Starting backup process..."
	print ""

	if not options.nostop:
		stopBalancer(connection)
		
	backup_servers(hosts_to_backup, prefix_backup, options.userssh, options.keyssh, options.dbpath, options.outpath,options.directoryperdb)

	if not options.nostart:
		startBalancer(connection)

	print "Backup process finished"
	print ""

	print ""
 
if __name__ == '__main__':
	main()
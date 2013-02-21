mongodb-cluster-backup
======================

This is a python script for backing up mongodb clusters. This tool get connected to a mongos inside the cluster and try to get the sharding configuration from that server, once the sharding configuration is available the script select a secondary for each shard and make the backup in those secondaries.

The backup process is as following:
  * stop the balancer, this could be avoided using the --nostop option. In high writing environments keeping the balancer stopped is usually a good idea, because of that sometimes the balancer should not be stopped. 
  * connect to each secondary (in parallel using fabric).
  * stop the mongo service
  * make a mongodump from the data folder to the output folder
  * build a tar file for the output folder
  * gzip the tar file
  * start the mongo service
  * start the balancer, In high writing environments keeping the balancer stopped is usually a good idea, for that kind of environment it is possible to avoid starting the balancer using the --nostart option.

The script can connect to authenticated mongo environments, if you do not give the username and password the script will connect as unauthenticated.

The connection to the secondaries is made over SSH, for that it is required and username and the path to the ssh private key, the user must be a SUDOER in order to stop the mongo service.


Requirements:

In order to make it easy, the script is based on tested and existing tools like:
  * pymongo, obviously to get connected to mongo (http://api.mongodb.org/python/current/). The easiest way to install it is by doing "sudo pip install pymongo"
  * fabric, fabric is a python library/command line tool that is really simple and powerful in order to administrate remotes systems (http://fabric.readthedocs.org/en/1.5/).  The easiest way to install it by is doing "sudo pip install fabric"


Usage: backup.py [options]

Options:
  * -h, --help, show the help message and exit
  * -s SERVER, --server=SERVER, mongos server that will be use as source of config.
  * -l PORT, --port=PORT, port where the mongos server is listening.
  * -u USER, --user=USER, user for establish the connection if mongo has authentication enabled.
  * -p PASSWORD, --password=PASSWORD, password for the user to establish the connection.
  * -a USERSSH, --userssh=USERSSH, user that will be use to establish the ssh connection to the secondaries. this user should be able to do SUDO
  * -k KEYSSH, --keyssh=KEYSSH, ssh private key to be use in the ssh connection.
  * -f, --nostop, this says if the balancer should not be stopped, if this parameter is given the tool assumes that the balancer is stopped.
  * -g, --nostart, this says if the balancer should not be started.
  * -d DBPATH, --dbpath=DBPATH, location of the data into the secondaries (mongod data path).
  * -o OUTPATH, --outpath=OUTPATH, location where the backup will be stored, a folder will be created inside this path for current backup.
  * -r, --directoryperdb, if this option is present indicates that the mongo data nodes are using the --directoryperdb option.


# coding=utf-8
# Copyright © The Delatex Authors. All rights reserved.

# Generic/Built-in Imports
import sys, os, gc, re, traceback, argparse, logging, platform, time, socket
from datetime import datetime
from collections import namedtuple
from pathlib import Path
from copy import deepcopy

# Third-Party Imports
import anyconfig
import colorama
import getpass 
import pygit2
import pymongo
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError, ConnectionFailure

# Constants
hostname = socket.gethostname().lower()
username = getpass.getuser().lower() 
user_home = Path().home()
cwd = Path(".").cwd()
json_dir = cwd / 'json'
current_repo = pygit2.Repository(".")
data_models = json_dir / 'data_models'
configs = anyconfig.load(cwd / 'configs.toml')
config_file = configs[hostname][username][0]['config_path']

# Adding required paths
sys.path.insert(0, str(cwd / 'cython'))

# Local Imports
from latex import LaTeX
from lib.helpers import (stream, save, abspath, detect_encoding, filesiter, load_json,\
    load_pickle, translate_arxiv_categories, print_summary, CrlfFlag, DebugLog)


def mongodb_connection(max_pool_size=1000):
    """Obtains a connection to a MongoDB. """
    client, connected = None, False
    config = anyconfig.load(config_file)
    db_config = config['database']
    credentials = config['credentials']

    try:
        client = MongoClient(
           host=db_config['host'],
           port=db_config['port'],
           username=credentials['username'],
           password=credentials['password'],
           authSource=db_config['db'],
           authMechanism=credentials['authMechanism'],
           tz_aware=True,
           maxPoolSize=max_pool_size
        )

        client.server_info()

        connected = True
        print("Connected successfully to the MongoDB!", file=sys.stdout, flush=True)

    except pymongo.errors.PyMongoError as ex:
        print(ex, file=sys.stderr, flush=True)
    finally:
        if not connected:
            sys.exit(1)
        return client

# Public Symbols
__all__ = [
           "mongodb_connection", "LaTeX", "stream", "save", "gc", "traceback", "argparse", "platform", "datetime", 
           "time", "namedtuple", "Path", "deepcopy", "abspath", "detect_encoding", "filesiter", "load_json",
           "load_pickle", "translate_arxiv_categories", "print_summary", "CrlfFlag", "DebugLog", "user_home", 
           "cwd", "current_repo", "data_models", "MongoClient", "ASCENDING", "DESCENDING", "Database", "Collection", 
           "BulkWriteError", "ConnectionFailure", "re", "json_dir", "colorama", "sys", "os", "hostname", "username"
          ]

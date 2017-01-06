import copy
import os

# from functools import reduce
# PORT_NUMBER = reduce(lambda x, y: x * y, map(ord, 'BigchainDB')) % 2**16
# basically, the port number is 9984
config = {
    'server': {
        # Note: this section supports all the Gunicorn settings:
        #       - http://docs.gunicorn.org/en/stable/settings.html
        'bind': os.environ.get('BIGCHAINDB_SERVER_BIND') or 'localhost:9984',
        'workers': None,  # if none, the value will be cpu_count * 2 + 1
        'threads': None,  # if none, the value will be cpu_count * 2 + 1
    },
    'database': {
        'host': os.environ.get('BIGCHAINDB_DATABASE_HOST', 'localhost'),
        'port': 28015,
        'name': 'bigchain_order',
    },
    'keypair': {
        'public': None,
        'private': None,
    },
    'keyring': [],
    'statsd': {
        'host': 'localhost',
        'port': 8125,
        'rate': 0.01,
    },
    'api_endpoint': os.environ.get('BIGCHAINDB_API_ENDPOINT') or 'http://localhost:9984/api/v1',
    'backlog_reassign_delay': 30,
    'restore_server': {
        'bind': os.environ.get('BIGCHAINDB_RESTORE_SERVER_BIND') or 'localhost:9986',
        'compress': True, # if compress, compress the response data
        'workers': None,  # if none, the value will be int(cpu_count/2) + 2
        'threads': None,  # if none, the value will be int(cpu_count/2) + 2
    },
    'restore_endpoint': os.environ.get('BIGCHAINDB_RESTORE_ENDPOINT') or 'http://localhost:9986/api/v1/collect',
}


# We need to maintain a backup copy of the original config dict in case
# the user wants to reconfigure the node. Check ``bigchaindb.config_utils``
# for more info.
_config = copy.deepcopy(config)
from bigchaindb.core import Bigchain  # noqa
from bigchaindb.version import __version__  # noqa

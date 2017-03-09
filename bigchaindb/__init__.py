import copy
import os

# for multi apps, you should specify the app service name, setup_name and database.name
# and modify the port in server.bind, api_endpoint, restore_server.bind, restore_endpoint
# and make them unique and free

from bigchaindb.base_config import unichain_config

# from functools import reduce
# PORT_NUMBER = reduce(lambda x, y: x * y, map(ord, 'BigchainDB')) % 2**16
# basically, the port number is 9984
config = {
    'app': {
        'setup_name': '{}'.format(unichain_config['server_config']['setup_name']),  # BigchainDB
        'service_name': '{}'.format(unichain_config['server_config']['service_name']),  # unichain
    },
    'server': {
        # Note: this section supports all the Gunicorn settings:
        #       - http://docs.gunicorn.org/en/stable/settings.html
        'bind': os.environ.get('BIGCHAINDB_SERVER_BIND') or 'localhost:{}'.format(unichain_config['server_config']['server_port']),
        'workers': None,  # if none, the value will be cpu_count * 2 + 1
        'threads': None,  # if none, the value will be cpu_count * 2 + 1
    },
    'database': {
        'host': os.environ.get('BIGCHAINDB_DATABASE_HOST', 'localhost'),
        'port': 28015,
        'name': '{}'.format(unichain_config['server_config']['db_name']),
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
    'api_endpoint': os.environ.get('BIGCHAINDB_API_ENDPOINT') or 'http://localhost:{}/uniledger/v1'
        .format(unichain_config['server_config']['server_port']),
    'backlog_reassign_delay': 30,
    'logger_config' : {
        'debug_to_console' : False,
        'debug_to_file' : False
    },
    'argument_config' : {
        'txs_length' : 1000,
        'pipe_maxsize' : 2000
    },
    'restore_server': {
        'bind': os.environ.get('BIGCHAINDB_RESTORE_SERVER_BIND') or 'localhost:{}'
            .format(unichain_config['server_config']['restore_server_port']),
        'compress': True, # if compress, compress the response data
        'workers': None,  # if none, the value will be int(cpu_count/2) + 2
        'threads': None,  # if none, the value will be int(cpu_count/2) + 2
    },
    'restore_endpoint': os.environ.get('BIGCHAINDB_RESTORE_ENDPOINT') or
                        'http://localhost:{}/uniledger/v1/collect'.format(unichain_config['server_config']['restore_server_port']),
}


# We need to maintain a backup copy of the original config dict in case
# the user wants to reconfigure the node. Check ``bigchaindb.config_utils``
# for more info.
_config = copy.deepcopy(config)
from bigchaindb.core import Bigchain  # noqa
from bigchaindb.version import __version__  # noqa

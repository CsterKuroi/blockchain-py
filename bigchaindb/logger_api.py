
import os
import datetime
import logging.config
import bigchaindb
app_service_name = bigchaindb.config['app']['service_name']
app_setup_name = bigchaindb.config['app']['setup_name']

####log configure####
BASE_DIR = os.path.expandvars('$HOME')
LOG_DIR = os.path.join(BASE_DIR, "{}_log".format(app_service_name))
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR) 
API_LOG_FILE = "{}_api.log.{}".format(app_service_name, datetime.datetime.now().strftime("%Y%m%d%H%M%S"))

LOG_CONF = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            'format': '%(asctime)s [%(name)s:%(lineno)d] [%(levelname)s] %(message)s'
        },
        'standard': {
            'format': '%(asctime)s [%(threadName)s:%(thread)d] [%(name)s:%(lineno)d] [%(levelname)s] %(message)s'
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "simple",
            "stream": "ext://sys.stdout"
        },
        "api": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "standard",
            "filename": os.path.join(LOG_DIR, API_LOG_FILE),
            'mode': 'w+',
            "maxBytes": 1024*1024*512, 
            "backupCount": 20,
            "encoding": "utf8"
        }
    },
    "loggers": {
         "unichain_api": {
             "level": "INFO",
             "handlers": ["console", "api"],
             "propagate": True
         }
    },
    "root": {
        'handlers': ["console","api"],
        'level': "DEBUG",
        'propagate': False
    }
}
logging.config.dictConfig(LOG_CONF)

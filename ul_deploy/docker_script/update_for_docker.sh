#! /bin/bash

# The set -e option instructs bash to immediately exit
# if any command has a non-zero exit status
set -e

source ./blockchain_nodes_conf_util.sh
source ./common_lib.sh

CLUSTER_BIGCHAIN_COUNT=`get_cluster_nodes_num`
[ $CLUSTER_BIGCHAIN_COUNT -eq 0 ] && {
    echo -e "[ERROR] blockchain_nodes num is 0"
    exit 1
}


INSTALL_FLAG=false
LOAD_FLAG=false

while getopts "il" arg
do
    case $arg in
        i)
            INSTALL_FLAG=true
        ;;
        l)
            LOAD_FLAG=true
        ;;
        *)
            echo "Usage: run_docker [-i] [-l]"
            echo "-i: install docker & docker compose; -l: load new docker image"
            exit 1
        ;;
    esac
done
echo "1"
##check blocknodes_conf format
echo -e "[INFO]==========check cluster nodes conf=========="
check_cluster_nodes_conf || {
    echo -e "[ERROR] $FUNCNAME execute fail!"
    exit 1
}

echo -e "[INFO]==========cluster nodes info=========="
cat $CLUSTER_CHAINNODES_CONF|grep -vE "^#|^$"
echo -e ""

echo -e "[WARNING]please confirm cluster nodes info: [y/n]"
read cluster_str
if [ "`echo "$cluster_str"|tr A-Z  a-z`" == "y" -o "`echo "$cluster_str"|tr A-Z  a-z`" == "yes" ];then
     echo -e "[INFO]=========begin update unichain=========="
else
    echo -e "[ERROR]input invalid or cluster nodes info invalid"
    echo -e "[ERROR]=========update unichain aborted==========="
    exit 1
fi

CLUSTER_BIGCHAIN_COUNT=`get_cluster_nodes_num`
[ $CLUSTER_BIGCHAIN_COUNT -eq 0 ] && {
    echo -e "[ERROR] blockchain_nodes num is 0"
    exit 1
}

#init env:python3 fabric3
echo -e "[INFO]=============init control machine env============="
./run_init_env.sh


echo -e "[INFO]============update unichain docker images============"
# clear old docker images and container
fab clear_unichain_docker_images
# send and load unichain_bdb.rar
fab update_unichain_images

echo -e "[INFO]============down docker images============"


echo -e "[INFO]============start rethinkdb============"
fab start_docker_rdb

echo -e "[INFO]============start unichain and unichain_api============"
fab start_docker_bdb

echo -e "[INFO]=========down  first_setup=========="
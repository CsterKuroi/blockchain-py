"""Backend implementation for RethinkDB.

This module contains all the methods to store and retrieve data from RethinkDB.
"""

from time import time

import rethinkdb as r

from bigchaindb import util
from bigchaindb.db.utils import Connection
from bigchaindb.common import exceptions


class RethinkDBBackend:

    def __init__(self, host=None, port=None, db=None):
        """Initialize a new RethinkDB Backend instance.

        Args:
            host (str): the host to connect to.
            port (int): the port to connect to.
            db (str): the name of the database to use.
        """

        self.read_mode = 'majority'
        self.durability = 'soft'
        self.connection = Connection(host=host, port=port, db=db)

    def write_transaction(self, signed_transaction):
        """Write a transaction to the backlog table.

        Args:
            signed_transaction (dict): a signed transaction.

        Returns:
            The result of the operation.
        """
        return self.connection.run(
                r.table('backlog')
                .insert(signed_transaction, durability=self.durability))

    def update_transaction(self, transaction_id, doc):
        """Update a transaction in the backlog table.

        Args:
            transaction_id (str): the id of the transaction.
            doc (dict): the values to update.

        Returns:
            The result of the operation.
        """

        return self.connection.run(
                r.table('backlog')
                .get(transaction_id)
                .update(doc))

    def delete_transaction(self, *transaction_id):
        """Delete a transaction from the backlog.

        Args:
            *transaction_id (str): the transaction(s) to delete

        Returns:
            The database response.
        """

        return self.connection.run(
                r.table('backlog')
                .get_all(*transaction_id)
                .delete(durability='hard'))

    def get_stale_transactions(self, reassign_delay):
        """Get a cursor of stale transactions.

        Transactions are considered stale if they have been assigned a node,
        but are still in the backlog after some amount of time specified in the
        configuration.

        Args:
            reassign_delay (int): threshold (in seconds) to mark a transaction stale.

        Returns:
            A cursor of transactions.
        """

        return self.connection.run(
                r.table('backlog')
                .filter(lambda tx: time() - tx['assignment_timestamp'] > reassign_delay))

    def get_transaction_from_block(self, transaction_id, block_id):
        """Get a transaction from a specific block.

        Args:
            transaction_id (str): the id of the transaction.
            block_id (str): the id of the block.

        Returns:
            The matching transaction.
        """
        return self.connection.run(
                r.table('bigchain', read_mode=self.read_mode)
                .get(block_id)
                .get_field('block')
                .get_field('transactions')
                .filter(lambda tx: tx['id'] == transaction_id))[0]

    def get_transaction_from_backlog(self, transaction_id):
        """Get a transaction from backlog.

        Args:
            transaction_id (str): the id of the transaction.

        Returns:
            The matching transaction.
        """
        return self.connection.run(
                r.table('backlog')
                .get(transaction_id)
                .without('assignee', 'assignment_timestamp')
                .default(None))

    def get_blocks_status_from_transaction(self, transaction_id):
        """Retrieve block election information given a secondary index and value

        Args:
            value: a value to search (e.g. transaction id string, payload hash string)
            index (str): name of a secondary index, e.g. 'transaction_id'

        Returns:
            :obj:`list` of :obj:`dict`: A list of blocks with with only election information
        """

        return self.connection.run(
                r.table('bigchain', read_mode=self.read_mode)
                .get_all(transaction_id, index='transaction_id')
                .pluck('votes', 'id', {'block': ['voters']}))

    def get_transactions_by_metadata_id(self, metadata_id):
        """Retrieves transactions related to a metadata.

        When creating a transaction one of the optional arguments is the `metadata`. The metadata is a generic
        dict that contains extra information that can be appended to the transaction.

        To make it easy to query the bigchain for that particular metadata we create a UUID for the metadata and
        store it with the transaction.

        Args:
            metadata_id (str): the id for this particular metadata.

        Returns:
            A list of transactions containing that metadata. If no transaction exists with that metadata it
            returns an empty list `[]`
        """
        return self.connection.run(
                r.table('bigchain', read_mode=self.read_mode)
                .get_all(metadata_id, index='metadata_id')
                .concat_map(lambda block: block['block']['transactions'])
                .filter(lambda transaction: transaction['transaction']['metadata']['id'] == metadata_id))

    def get_transactions_by_asset_id(self, asset_id):
        """Retrieves transactions related to a particular asset.

        A digital asset in bigchaindb is identified by an uuid. This allows us to query all the transactions
        related to a particular digital asset, knowing the id.

        Args:
            asset_id (str): the id for this particular metadata.

        Returns:
            A list of transactions containing related to the asset. If no transaction exists for that asset it
            returns an empty list `[]`
        """

        return self.connection.run(
            r.table('bigchain', read_mode=self.read_mode)
             .get_all(asset_id, index='asset_id')
             .concat_map(lambda block: block['block']['transactions'])
             .filter(lambda transaction: transaction['transaction']['asset']['id'] == asset_id))

    def get_spent(self, transaction_id, condition_id):
        """Check if a `txid` was already used as an input.

        A transaction can be used as an input for another transaction. Bigchain needs to make sure that a
        given `txid` is only used once.

        Args:
            transaction_id (str): The id of the transaction.
            condition_id (int): The index of the condition in the respective transaction.

        Returns:
            The transaction that used the `txid` as an input else `None`
        """

        # TODO: use index!
        return self.connection.run(
                r.table('bigchain', read_mode=self.read_mode)
                .concat_map(lambda doc: doc['block']['transactions'])
                .filter(lambda transaction: transaction['transaction']['fulfillments'].contains(
                    lambda fulfillment: fulfillment['input'] == {'txid': transaction_id, 'cid': condition_id})))

    def get_owned_ids(self, owner):
        """Retrieve a list of `txids` that can we used has inputs.

        Args:
            owner (str): base58 encoded public key.

        Returns:
            A cursor for the matching transactions.
        """

        # TODO: use index!
        return self.connection.run(
                r.table('bigchain', read_mode=self.read_mode)
                .concat_map(lambda doc: doc['block']['transactions'])
                .filter(lambda tx: tx['transaction']['conditions'].contains(
                    lambda c: c['owners_after'].contains(owner))))

    def get_votes_by_block_id(self, block_id):
        """Get all the votes casted for a specific block.

        Args:
            block_id (str): the block id to use.

        Returns:
            A cursor for the matching votes.
        """
        return self.connection.run(
                r.table('votes', read_mode=self.read_mode)
                .between([block_id, r.minval], [block_id, r.maxval], index='block_and_voter'))

    def get_votes_by_block_id_and_voter(self, block_id, node_pubkey):
        """Get all the votes casted for a specific block by a specific voter.

        Args:
            block_id (str): the block id to use.
            node_pubkey (str): base58 encoded public key

        Returns:
            A cursor for the matching votes.
        """
        return self.connection.run(
                r.table('votes', read_mode=self.read_mode)
                .get_all([block_id, node_pubkey], index='block_and_voter'))

    def write_block(self, block, durability='soft'):
        """Write a block to the bigchain table.

        Args:
            block (dict): the block to write.

        Returns:
            The database response.
        """
        return self.connection.run(
                r.table('bigchain')
                .insert(r.json(block), durability=durability))

    def has_transaction(self, transaction_id):
        """Check if a transaction exists in the bigchain table.

        Args:
            transaction_id (str): the id of the transaction to check.

        Returns:
            ``True`` if the transaction exists, ``False`` otherwise.
        """
        return bool(self.connection.run(
                r.table('bigchain', read_mode=self.read_mode)
                .get_all(transaction_id, index='transaction_id').count()))

    def count_blocks(self):
        """Count the number of blocks in the bigchain table.

        Returns:
            The number of blocks.
        """

        return self.connection.run(
                r.table('bigchain', read_mode=self.read_mode)
                .count())

    def count_backlog_txs(self):
        """Count the number of txs in the backlog table.

        Returns:
            The number of txs.
        """

        return self.connection.run(
                r.table('backlog', read_mode=self.read_mode)
                .count())

    def write_vote(self, vote):
        """Write a vote to the votes table.

        Args:
            vote (dict): the vote to write.

        Returns:
            The database response.
        """
        return self.connection.run(
                r.table('votes')
                .insert(vote))

    def get_last_voted_block(self, node_pubkey):
        """Get the last voted block for a specific node.

        Args:
            node_pubkey (str): base58 encoded public key.

        Returns:
            The last block the node has voted on. If the node didn't cast
            any vote then the genesis block is returned.
        """
        try:
            # get the latest value for the vote timestamp (over all votes)
            max_timestamp = self.connection.run(
                    r.table('votes', read_mode=self.read_mode)
                    .filter(r.row['node_pubkey'] == node_pubkey)
                    .max(r.row['vote']['timestamp']))['vote']['timestamp']

            last_voted = list(self.connection.run(
                r.table('votes', read_mode=self.read_mode)
                .filter(r.row['vote']['timestamp'] == max_timestamp)
                .filter(r.row['node_pubkey'] == node_pubkey)))

        except r.ReqlNonExistenceError:
            # return last vote if last vote exists else return Genesis block
            return self.connection.run(
                r.table('bigchain', read_mode=self.read_mode)
                .filter(util.is_genesis_block)
                .nth(0))

        # Now the fun starts. Since the resolution of timestamp is a second,
        # we might have more than one vote per timestamp. If this is the case
        # then we need to rebuild the chain for the blocks that have been retrieved
        # to get the last one.

        # Given a block_id, mapping returns the id of the block pointing at it.
        mapping = {v['vote']['previous_block']: v['vote']['voting_for_block']
                   for v in last_voted}

        # Since we follow the chain backwards, we can start from a random
        # point of the chain and "move up" from it.
        last_block_id = list(mapping.values())[0]

        # We must be sure to break the infinite loop. This happens when:
        # - the block we are currenty iterating is the one we are looking for.
        #   This will trigger a KeyError, breaking the loop
        # - we are visiting again a node we already explored, hence there is
        #   a loop. This might happen if a vote points both `previous_block`
        #   and `voting_for_block` to the same `block_id`
        explored = set()

        while True:
            try:
                if last_block_id in explored:
                    raise exceptions.CyclicBlockchainError()
                explored.add(last_block_id)
                last_block_id = mapping[last_block_id]
            except KeyError:
                break

        return self.connection.run(
                r.table('bigchain', read_mode=self.read_mode)
                .get(last_block_id))

    def get_unvoted_blocks(self, node_pubkey):
        """Return all the blocks that have not been voted by the specified node.

        Args:
            node_pubkey (str): base58 encoded public key

        Returns:
            :obj:`list` of :obj:`dict`: a list of unvoted blocks
        """

        unvoted = self.connection.run(
                r.table('bigchain', read_mode=self.read_mode)
                .filter(lambda block: r.table('votes', read_mode=self.read_mode)
                                       .get_all([block['id'], node_pubkey], index='block_and_voter')
                                       .is_empty())
                .order_by(r.asc(r.row['block']['timestamp'])))

        # FIXME: I (@vrde) don't like this solution. Filtering should be done at a
        #        database level. Solving issue #444 can help untangling the situation
        unvoted_blocks = filter(lambda block: not util.is_genesis_block(block), unvoted)
        return unvoted_blocks

    # TODO 需要写一些通用方法，提高代码重用

    def delete_heartbeat(self,node_pubkey):
        return self.connection.run(r.table('heartbeat').filter({'node_publickey': node_pubkey}).delete())

    def init_heartbeat(self,data):
        return self.connection.run(r.table('heartbeat').insert(data))

    def isReassignnodeExist(self):
        return self.connection.run(r.table('reassignnode').count())

    def init_reassignnode(self,data):
        return self.connection.run(r.table('reassignnode').insert(data))

    def updateHeartbeat(self,node_pubkey,time):
        return self.connection.run(r.table('heartbeat').filter({'node_publickey': node_pubkey}).update({'timestamp':time}))

    def getAssigneekey(self):
        return self.connection.run(r.table('reassignnode'))

    def updateAssigneebeat(self,node_pubkey,time):
        return self.connection.run(r.table('reassignnode').filter({'node_publickey': node_pubkey}).update({'timestamp':time}))

    def is_assignee_alive(self,assigneekey):
        return self.connection.run(r.table('reassignnode').filter({'node_publickey': assigneekey}))

    def is_node_alive(self,txpublickey):
        return self.connection.run(r.table('heartbeat').filter({'node_publickey': txpublickey}))

    def update_assign_node(self,updateid,next_assign_node):
        return self.connection.run(r.table('reassignnode').update({"nodeid":updateid,'node_publickey':next_assign_node,'timestamp':time()}))

    def insertRewrite(self,data):
        return self.connection.run(r.table('rewrite').insert(data))

    def isBlockRewrited(self,id):
        return self.connection.run(r.table('rewrite').filter({'id': id}).count())

    ##############################################
    ####    unichain api query method     ########
    ##############################################
    def get_block_by_id(self, block_id):
        #return self.connection.run(r.table('bigchain', read_mode=self.read_mode).filter({'id':block_id}))
        return self.connection.run(
            r.table('bigchain', read_mode=self.read_mode)
             .get(block_id))

    def get_transaction_createavgtime_by_range(self, begintime, endtime):
        time_range = int(endtime) - int(begintime)
        if time_range <= 0:
            return 0,False
        # transaction_count =  self.connection.run(
        #     r.table('bigchain', read_mode=self.read_mode)
        #      .between(begintime, endtime, index='tx_timestamp').count())  # tx time
        transaction_count = self.connection.run(r.table("bigchain").concat_map(lambda block: block['block']['transactions']).filter((r.row["transaction"]['timestamp'] > begintime) & (r.row["transaction"]['timestamp'] < endtime)).count())
        if not transaction_count:
            return 0,False
        return round(time_range/transaction_count,3),True
   
    def get_block_createavgtime_by_range(self, begintime, endtime):
        time_range = int(endtime) - int(begintime)
        if time_range <= 0:
            return 0,False
        block_count =  self.connection.run(r.table('bigchain', read_mode=self.read_mode).between(begintime, endtime, index='block_timestamp').count())  # block time
        if not block_count:
            return 0,False
        return round(time_range/block_count,3),True

    def get_vote_time_by_blockid(self, block_id):
        vote_begin_time = self.connection.run(r.table('bigchain', read_mode=self.read_mode).get(block_id).get_field('block').get_field('timestamp'))
        vote_end_time = self.connection.run(r.table('votes').filter(r.row['vote']['voting_for_block'] == block_id).max(r.row['vote']['timestamp']).get_field('vote').get_field('timestamp'))
        print(vote_begin_time)
        print(vote_end_time)
        vote_time = int(vote_end_time) - int(vote_begin_time)
        if not vote_time:
            vote_time = 1
        return vote_time,True

    def get_vote_avgtime_by_range(self, begintime, endtime):     
        time_range = int(endtime) - int(begintime)
        if time_range <= 0:
            return 0,False
        vote_count =  self.connection.run(r.table('votes', read_mode=self.read_mode).between(begintime, endtime, index='vote_timestamp').get_field('vote').get_field('voting_for_block').distinct().count())
        if not vote_count:
            return 0,False
        return round(time_range/vote_count,3),True


    # @author lz for api

    def get_txNumberById(self, block_id):
        """Get the numbers of the special block by block_id.
        If the block not exists, return 0.

        :param block_id:
        :return:
        """

        return self.connection.run(r.table('bigchain').get_all(block_id, index='id').concat_map(lambda block: block['block']['transactions']).count())

    def get_txNumber(self, startTime=r.minval, endTime=r.maxval):
        """Get the numbers of the special block by the index block_timestamp.
        If no block exist between that, return 0.

        :param startTime:
        :param endtime:
        :return:
        """

        return self.connection.run(r.table('bigchain').between(
            startTime, endTime, index='block_timestamp', left_bound='closed',
            right_bound='closed').map(lambda block: block['block']['transactions'].count()).sum())

    def get_BlockNumber(self, startTime=r.minval, endTime=r.maxval):
        return self.connection.run(r.table('bigchain').between(startTime, endTime, index="block_timestamp").count())

    def get_allInvalidBlock(self,limit=None):
        if limit==None:
            return self.connection.run(r.table('rewrite').order_by(r.desc(r.row['timestamp'])).get_field('id'))
        else:
            return self.connection.run(r.table('rewrite').order_by(r.desc(r.row['timestamp'])).get_field('id').limit(1000))

    # def get_invalidBlockByS(self,startTime):
    #     return self.connection.run(r.table('rewrite').between(startTime, r.maxval, index='block_timestamp').get_field('id'))
    #
    # def get_invalidBlockByE(self,endtime):
    #     return self.connection.run(r.table('rewrite').between(r.minval, endtime, index='block_timestamp').get_field('id'))

    def get_invalidBlockByTime(self,startTime,endTime):
        return self.connection.run(r.table('rewrite').between(startTime, endTime, index='block_timestamp').get_field('id'))

    def get_BlockIdList(self,startTime=r.minval,endTime=r.maxval,limit=None):
        if limit == None:
            return self.connection.run(r.table('bigchain').between(startTime, endTime, index='block_timestamp').order_by(index=r.desc('block_timestamp')).get_field('id'))
        else:
            return self.connection.run(r.table('bigchain').between(startTime, endTime, index='block_timestamp').order_by(index=r.desc('block_timestamp')).get_field('id').limit(limit))

    def get_txIdList(self, startTime=r.minval, endTime=r.maxval, limit=None):
        if limit == None:
            return self.connection.run(r.table("bigchain").concat_map(lambda block: block['block']['transactions']).order_by(r.desc(r.row['block']['transactions']['transaction']['timestamp'])).filter((r.row["transaction"]['timestamp'] >= startTime) and (r.row["transaction"]['timestamp'] <= endTime)))
        else:
            return self.connection.run(r.table("bigchain").concat_map(lambda block: block['block']['transactions']).order_by(r.desc(r.row['block']['transactions']['transaction']['timestamp'])).filter((r.row["transaction"]['timestamp'] >= startTime) and (r.row["transaction"]['timestamp'] <= endTime)).limit(limit))

    def get_txNumberOfEachBlock(self,limit=None):
        if limit == None:
            return self.connection.run(r.table("bigchain").map({'id':r.row['id'],'count':r.row['block']['transactions'].count()}))
        else:
            return self.connection.run(r.table("bigchain").order_by(index=r.desc('block_timestamp')).map({'id':r.row['id'],'count':r.row['block']['transactions'].count()}).limit(limit))

    def get_block(self,block_id):
        return self.connection.run(r.table('bigchain').get(block_id))

    def get_tx_by_id(self,tx_id):
        return self.connection.run(r.table('bigchain').get_all(tx_id,index='transaction_id'))






















"""This module takes care of all the logic related to block voting.

The logic is encapsulated in the ``Vote`` class, while the sequence
of actions to do on transactions is specified in the ``create_pipeline``
function.
"""

import logging
from collections import Counter

from multipipes import Pipeline, Node
from bigchaindb.monitor import Monitor
from bigchaindb.common import exceptions

from bigchaindb.consensus import BaseConsensusRules
from bigchaindb.models import Transaction, Block
from bigchaindb.pipelines.utils import ChangeFeed
from bigchaindb import Bigchain, config
import time

monitor = Monitor()

logger = logging.getLogger(__name__)


class Vote:
    """This class encapsulates the logic to vote on blocks.

    Note:
        Methods of this class will be executed in different processes.
    """

    def __init__(self):
        """Initialize the Block voter."""

        # Since cannot share a connection to RethinkDB using multiprocessing,
        # we need to create a temporary instance of BigchainDB that we use
        # only to query RethinkDB
        self.consensus = BaseConsensusRules

        # This is the Bigchain instance that will be "shared" (aka: copied)
        # by all the subprocesses
        self.bigchain = Bigchain()
        self.last_voted_id = Bigchain().get_last_voted_block().id

        self.counters = Counter()
        self.validity = {}

        self.invalid_dummy_tx = Transaction.create([self.bigchain.me],
                                                   [([self.bigchain.me], 1)])

    def validate_block(self, block):
        # wsp@monitor
        begin_time = int(round(time.time() * 1000))
        logger.debug("Start validating block %s", block['id'])
        time1 = int(round(time.time() * 1000))
        if not self.bigchain.has_previous_vote(block['id'], block['block']['voters']):
            try:
                block = Block.from_dict(block)
                time2 = int(round(time.time() * 1000))
                logger.debug("Block from_dict cost %s", time2 - time1)
            except exceptions.InvalidHash:
                # XXX: if a block is invalid we should skip the `validate_tx`
                # step, but since we are in a pipeline we cannot just jump to
                # another function. Hackish solution: generate an invalid
                # transaction and propagate it to the next steps of the
                # pipeline.
                return block['id'], [self.invalid_dummy_tx], begin_time
            try:
                # zy@secn
                if monitor is not None:
                    # with monitor.timer('validate_block', rate=config['statsd']['rate']):
                    with monitor.timer('validate_block'):
                        time3 = int(round(time.time() * 1000))
                        block._validate_block(self.bigchain)
                        time4 = int(round(time.time() * 1000))
                        logger.debug("JUST validating block cost %s", time4 - time3)
                        # self.consensus.validate_block(self.bigchain, block)
                else:
                    block._validate_block(self.bigchain)
                    # self.consensus.validate_block(self.bigchain, block)
                    # self.consensus.validate_block(self.bigchain, block)
            except (exceptions.OperationError,
                    exceptions.InvalidSignature):
                # XXX: if a block is invalid we should skip the `validate_tx`
                # step, but since we are in a pipeline we cannot just jump to
                # another function. Hackish solution: generate an invalid
                # transaction and propagate it to the next steps of the
                # pipeline.
                return block.id, [self.invalid_dummy_tx], begin_time
            logger.debug("End validating block %s, cost :%s", block.id, int(round(time.time() * 1000)) - begin_time)
            return block.id, block.transactions, begin_time

    def ungroup(self, block_id, transactions, begin_time):
        """Given a block, ungroup the transactions in it.

        Args:
            block_id (str): the id of the block in progress.
            transactions (list(Transaction)): transactions of the block in
                progress.
            begin_time(int):

        Returns:
            ``None`` if the block has been already voted, an iterator that
            yields a transaction, block id, and the total number of
            transactions contained in the block otherwise.
        """
        time1 = int(round(time.time() * 1000))
        logger.debug("Start ungroup block %s", block_id)
        num_tx = len(transactions)
        for tx in transactions:
            yield tx, block_id, num_tx, begin_time
        logger.debug("End ungroup block %s, cost:%s", block_id, int(round(time.time() * 1000)) - time1)

    def validate_tx(self, tx, block_id, num_tx, begin_time):
        """Validate a transaction.

        Args:
            tx (Transaction): the transaction to validate
            block_id (str): the id of block containing the transaction
            num_tx (int): the total number of transactions to process
            begin_time(int):

        Returns:
            Three values are returned, the validity of the transaction,
            ``block_id``, ``num_tx``.
        """
        logger.debug("Start Validate tx %s in block %s", tx.id, block_id)
        result = bool(self.bigchain.is_valid_transaction(tx))
        logger.debug("End Validate tx %s in block %s , %r", tx.id, block_id, result)
        return result, block_id, num_tx, begin_time

    def vote(self, tx_validity, block_id, num_tx, begin_time):
        """Collect the validity of transactions and cast a vote when ready.

        Args:
            tx_validity (bool): the validity of the transaction
            block_id (str): the id of block containing the transaction
            num_tx (int): the total number of transactions to process
            begin_time(int):

        Returns:
            None, or a vote if a decision has been reached.
        """
        logger.debug("Vote get %s/%s tx in block %s", self.counters[block_id] + 1, num_tx, block_id)
        self.counters[block_id] += 1
        self.validity[block_id] = tx_validity and self.validity.get(block_id,
                                                                    True)

        if self.counters[block_id] == num_tx:
            vote = self.bigchain.vote(block_id,
                                      self.last_voted_id,
                                      self.validity[block_id])
            self.last_voted_id = block_id
            del self.counters[block_id]
            del self.validity[block_id]
            return vote, begin_time

    def write_vote(self, vote, begin_time):
        """Write vote to the database.

        Args:
            vote: the vote to write.
            begin_time(int):
        """
        validity = 'valid' if vote['vote']['is_block_valid'] else 'invalid'
        logger.info("Vote '%s' block %s , node_pubkey = %s", validity,
                    vote['vote']['voting_for_block'], vote['node_pubkey'])
        end_time = int(round(time.time() * 1000))
        vote_time = end_time - begin_time
        if monitor is not None:
            with monitor.timer('write_vote'):
                self.bigchain.write_vote(vote)
                monitor.gauge('vote_time', value=vote_time)
        else:
            self.bigchain.write_vote(vote)
        logger.debug("Write vote down %s, total time %d", vote['vote']['voting_for_block'], vote_time)
        return vote


def initial():
    """Return unvoted blocks."""
    b = Bigchain()
    rs = b.get_unvoted_blocks()
    return rs


def get_changefeed():
    """Create and return the changefeed for the bigchain table."""

    return ChangeFeed('bigchain', operation=ChangeFeed.INSERT, prefeed=initial())


def create_pipeline():
    """Create and return the pipeline of operations to be distributed
    on different processes."""

    voter = Vote()

    vote_pipeline = Pipeline([
        Node(voter.validate_block,
             number_of_processes=config['argument_config']['vote_pipeline.validate_processes_num']),
        Node(voter.ungroup, number_of_processes=config['argument_config']['vote_pipeline.ungroup_processes_num']),
        Node(voter.validate_tx, fraction_of_cores=config['argument_config']['vote_pipeline.fraction_of_cores']),
        Node(voter.vote),
        Node(voter.write_vote)
    ])

    return vote_pipeline


def start():
    """Create, start, and return the block pipeline."""
    pipeline = create_pipeline()
    pipeline.setup(indata=get_changefeed())
    pipeline.start()
    return pipeline

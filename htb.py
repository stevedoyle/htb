import simpy

# TODO: Need to prioritise nodes that have not exceeded their rate above nodes
# that are > rate < ceil.
#
# Idea:
#   - List of nodes in the CAN_SEND state at each level
#   - List of nodes in the CAN_BORROW state at each level
#   - List of nodes in the CANT_SEND state at each level
#   - Iterate over the CAN_SEND nodes at lowest level & dequeue packets
#   - Change node state based on tokens consumed
#   - Only service CAN_BORROW nodes when no more CAN_SEND nodes
#   - Update states on each replenish
#   - Change of state means a change in list membership


class TokenBucketNode(object):

    def __init__(self, rate, ceil, parentBucket=None):
        # Token bucket parameters
        self.rate = rate
        self.ceil = ceil
        self.burst = rate
        self.cburst = ceil
        self.parentBucket = parentBucket
        self.tokens = self.burst  # Current size of the bucket in bytes
        self.ctokens = self.cburst  # Current size of the bucket in bytes
        self.update_time = 0.0  # Last time the bucket was updated
        self.state = HTB_CAN_SEND

    def replenish(self, timestamp):
        """ Add tokens to bucket based on current time """
        now = timestamp

        if self.parentBucket:
            self.parentBucket.replenish(now)

        self.tokens = min(self.burst, self.tokens +
                          self.rate * (now - self.update_time))
        self.ctokens = min(self.cburst, self.ctokens +
                           self.ceil * (now - self.update_time))
        self.update_time = now

    def consume(self, amount):
        if amount <= self.tokens - 100:
            self.tokens -= amount
            self.ctokens -= amount
            if self.parentBucket:
                self.parentBucket.account(amount)
            return True

        if self.parentBucket and (amount <= self.ctokens):
            borrowed = self.parentBucket.consume(amount)
            if borrowed:
                self.ctokens -= amount
                self.tokens = 0
                return True

        return False

    def account(self, amount):
        self.tokens -= amount
        self.ctokens -= amount


class ShaperTokenBucket(TokenBucketNode):
    """ Models an ideal token bucket shaper. Note the token bucket size should
    be greater than the size of the largest packet that can occur on input. If
    this is not the case we always accumulate enough tokens to let the current
    packet pass based on the average rate. This may not be the behavior you
    desire.

        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        rate : float
            the min token arrival rate in bits
        ceil : Number
            the max token arrival rate in bits

    """

    def __init__(self, env, rate, ceil, parentBucket=None, debug=False,
                 name=""):
        super().__init__(rate, ceil, parentBucket)

        # Simulation variables
        self.store = simpy.Store(env)
        self.env = env
        self.out = None

        # Statistics
        self.packets_rec = 0
        self.packets_sent = 0

        self.name = name
        self.debug = debug

        self.action = env.process(self.run())

        if self.debug:
            print("rate:%0.1f, ceil:%d, tokens:%d, burst:%d, ctokens:%d, cburst:%d" %
                  (self.rate, self.ceil, self.tokens, self.burst, self.ctokens,
                   self.cburst))

    def run(self):
        while True:
            msg = (yield self.get_msg())

            consumed = False
            while not consumed:
                self.replenish(self.env.now)

                if self.debug:
                    print(self.name + " %0.1f: (%d, %d), (%d, %d)" %
                          (self.env.now, self.tokens, self.ctokens,
                           self.parentBucket.tokens, self.parentBucket.ctokens))

                consumed = self.consume(msg.size)
                if not consumed:
                    # Need to wait for bucket to fill before consuming
                    # yield self.env.timeout((msg.size -
                    # self.ctokens)/self.ceil)
                    yield self.env.timeout(0.1)

            # Send packet
            self.send(msg)

    def put(self, pkt):
        self.packets_rec += 1
        return self.store.put(pkt)

    def get_msg(self):
        return self.store.get()

    def send(self, msg):
        self.out.put(msg)
        self.packets_sent += 1
        if self.debug:
            print('[%0.1f: %d, %d] ' %
                  (self.env.now, self.tokens, self.ctokens), msg)

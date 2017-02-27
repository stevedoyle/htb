import random


class TokenBucketNode(object):

    quantum = 100

    def __init__(self, name, rate, ceil, parent=None):
        self.name = name
        # Token bucket parameters
        self.rate = rate
        self.ceil = ceil
        self.burst = rate
        self.cburst = ceil
        self.parent = parent
        self.tokens = self.burst  # Current size of the bucket in bytes
        self.ctokens = self.cburst  # Current size of the bucket in bytes
        self.update_time = 0.0  # Last time the bucket was updated
        self.state = 'HTB_CAN_SEND'

    def replenish(self, timestamp):
        """ Add tokens to bucket based on current time """
        now = timestamp

        if self.parent:
            self.parent.replenish(now)

        elapsed = now - self.update_time
        self.tokens = min(self.burst, self.tokens + self.rate * elapsed)
        self.ctokens = min(self.cburst, self.ctokens + self.ceil * elapsed)
        self.update_time = now
        self.update_state()

    def account(self, amount):
        if amount > self.tokens and amount > self.ctokens:
            print("%s: Exceeding all tokens" % (self.name))

        self.tokens = max(0, self.tokens - amount)
        self.ctokens = max(0, self.ctokens - amount)
        self.update_state()
        if self.parent:
            self.parent.account(amount)

    def borrow(self):
        """ Borrowing is allowed in quantum units if there is enough tokens.
        Otherwise, attempt to borrow from the parent. """

        if self.can_send():
            return True

        if self.can_borrow():
            return self.borrow_from_parent()

        return False

    def borrow_from_parent(self):
        """ Try and borrow tokens from the parent. """
        return self.parent and self.parent.borrow()

    def update_state(self):
        if self.tokens >= self.quantum:
            self.state = 'HTB_CAN_SEND'
        elif self.ctokens >= self.quantum:
            self.state = 'HTB_CAN_BORROW'
        else:
            self.state = 'HTB_CANNOT_SEND'

    def cannot_send(self):
        return self.state == 'HTB_CANNOT_SEND'

    def can_send(self):
        status = (self.state == 'HTB_CAN_SEND')
        if self.parent:
            status &= self.parent.can_send()
        return status

    def can_borrow(self):
        status = (self.state == 'HTB_CAN_BORROW')
        if self.parent:
            status &= (self.parent.can_send()
                       | self.parent.can_borrow())
        return status


class ShaperTokenBucket(TokenBucketNode):

    def __init__(self, env, name, rate, ceil, parent=None, debug=False):
        super().__init__(name, rate, ceil, parent)

        # Simulation variables
        self.env = env
        self.inp = None
        self.outp = None
        self.msg_sent = self.env.event()
        self.msg = None

        # Statistics
        self.packets_sent = 0
        self.bytes_sent = 0

        self.name = name
        self.debug = debug

        self.action = env.process(self.run())

    def run(self):
        while True:
            self.msg = self.get_msg()
            yield self.msg_sent

    def get_msg(self):
        return self.inp.get()

    def send(self):
        self.account(self.msg.size)
        self.outp.put(self.msg)
        self.packets_sent += 1
        self.bytes_sent += self.msg.size
        self.msg = None
        self.msg_sent.succeed()
        self.msg_sent = self.env.event()

    def borrow_and_send(self):
        if self.borrow_from_parent():
            self.send()
            return True
        return False

    def has_packets(self):
        return self.msg is not None

    def stats(self, short=False):
        if short:
            return "%d" % (self.bytes_sent / self.env.now)
        else:
            return "%s: %d Bps" % (self.name, self.bytes_sent / self.env.now)


class RateLimiter(object):
    def __init__(self, env):
        self.shapers = []
        self.replenish_interval = 0.1

        self.env = env
        self.action = env.process(self.run())

    def add_shaper(self, shaper):
        self.shapers.append(shaper)

    def replenish(self):
        now = self.env.now
        for shaper in self.shapers:
            shaper.replenish(now)

    def run(self):
        while True:
            self.replenish()

            self.process_nodes_that_can_send1()
            self.process_nodes_that_can_borrow1()

            yield self.env.timeout(self.replenish_interval)

    def process_nodes_that_can_send1(self):
        random.shuffle(self.shapers)
        for shaper in self.shapers:
            while shaper.has_packets() and shaper.can_send():
                shaper.send()

    def process_nodes_that_can_send(self):
        while True:
            sent = False
            random.shuffle(self.shapers)
            for shaper in self.shapers:
                if shaper.has_packets() and shaper.can_send():
                    shaper.send()
                    sent = True
            if not sent:
                break

    def process_nodes_that_can_borrow1(self):
        random.shuffle(self.shapers)
        for shaper in self.shapers:
            while shaper.has_packets() and shaper.can_borrow():
                shaper.borrow_and_send()

    def process_nodes_that_can_borrow(self):
        while True:
            sent = False
            random.shuffle(self.shapers)
            for shaper in self.shapers:
                if shaper.has_packets() and shaper.can_borrow():
                    sent |= shaper.borrow_and_send()
            if not sent:
                break


class Packet(object):
    def __init__(self, size):
        self.size = size


class PacketGenerator(object):
    def __init__(self, name, sdist):
        self.name = name
        self.sdist = sdist
        self.packets_sent = 0
        self.bytes_sent = 0

    def get(self):
        self.packets_sent += 1
        p = Packet(self.sdist())
        self.bytes_sent += p.size
        return p


class PacketSink(object):
    def __init__(self, env, name):
        self.env = env
        self.name = name
        self.packets_recv = 0
        self.bytes_recv = 0
        self.last_arrival = 0.0

    def put(self, pkt):
        self.packets_recv += 1
        self.bytes_recv += pkt.size
        self.last_arrival = self.env.now

    def rate(self):
        return self.bytes_recv / self.last_arrival

    def stats(self):
        return "%s: %d Bps" % (self.name, self.rate())

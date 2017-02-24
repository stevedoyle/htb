"""
This file shows an example of a traffic shaper whose bucket size is
the same of the packet size and whose bucket rate is one half the input
packet rate.
In addition it shows a method of plotting packet arrival and exit times.
Copyright Dr. Greg M. Bernstein 2014
Released under the MIT license
"""
import simpy
import htb


def print_sink_stats(name, sink):
    print("[%s: %d bytes in %0.1f seconds (%d Bps)" %
          (name, sink.bytes_recv, sink.last_arrival,
           sink.bytes_recv/sink.last_arrival))


if __name__ == '__main__':
    def const_size():
        return 100.0

    env = simpy.Environment()

    pg = htb.PacketGenerator("Gen", const_size)
    ps1 = htb.PacketSink(env)
    ps2 = htb.PacketSink(env)

    root = htb.TokenBucketNode('Root', rate=800, ceil=800)
    shaper1 = htb.ShaperTokenBucket(env, 'S1', rate=300, ceil=800, parent=root,
                                    debug=False)
    shaper2 = htb.ShaperTokenBucket(env, 'S2', rate=200, ceil=800, parent=root,
                                    debug=False)

    shaper1.inp = pg
    shaper1.outp = ps1
    shaper2.inp = pg
    shaper2.outp = ps2

    rate_limiter = htb.RateLimiter(env)
    rate_limiter.add_shaper(shaper1)
    rate_limiter.add_shaper(shaper2)

    env.run(until=1000)

    print_sink_stats("S1", ps1)
    print_sink_stats("S2", ps2)

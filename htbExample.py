"""
This file shows an example of a traffic shaper whose bucket size is
the same of the packet size and whose bucket rate is one half the input
packet rate.
In addition it shows a method of plotting packet arrival and exit times.
Copyright Dr. Greg M. Bernstein 2014
Released under the MIT license
"""
import simpy

import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt

from SimComponents import PacketGenerator, PacketSink
from htb import ShaperTokenBucket

if __name__ == '__main__':
    def const_arrival():
        return 0.1

    def const_size():
        return 100.0
    env = simpy.Environment()
    pg = PacketGenerator(env, "SJSU", const_arrival, const_size, finish=20)
    pg2 = PacketGenerator(env, "SJSU", const_arrival, const_size, finish=20)
    pg3 = PacketGenerator(env, "SJSU", const_arrival, const_size, finish=20)
    ps = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)
    ps2 = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)
    ps3 = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)

    root = ShaperTokenBucket(env, rate=800, ceil=800)
    shaper1 = ShaperTokenBucket(env, rate=300, ceil=800, parentBucket=root,
                                name='S1')
    shaper2 = ShaperTokenBucket(env, rate=500, ceil=800, parentBucket=root,
                                name='S2')
    pg.out = ps

    pg2.out = shaper1
    shaper1.out = ps2

    pg3.out = shaper2
    shaper2.out = ps3

    env.run(until=10000)
    #print(ps.arrivals)
    print("[Shaper#1: %d bytes in %0.1f seconds (%0.1fbps)" %
          (ps2.bytes_rec, ps2.last_arrival, ps2.bytes_rec/ps2.last_arrival))
    print("[Shaper#2: %d bytes in %0.1f seconds (%0.1fbps)" %
          (ps3.bytes_rec, ps3.last_arrival, ps3.bytes_rec/ps3.last_arrival))

    #fig, axis = plt.subplots()
    #axis.vlines(ps.arrivals, 0.0, 1.0,colors="g", linewidth=2.0, label='input stream')
    #axis.vlines(ps2.arrivals, 0.0, 0.7, colors="r", linewidth=2.0, label='output stream')
    #axis.set_title("Arrival times")
    #axis.set_xlabel("time")
    #axis.set_ylim([0, 1.5])
    #axis.set_xlim([0, max(ps2.arrivals) + 10])
    #axis.legend()
    #axis.set_ylabel("normalized frequency of occurrence")
    #fig.savefig("ArrivalHistogram.png")
    #plt.show()

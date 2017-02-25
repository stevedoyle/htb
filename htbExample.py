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
from graphviz import Digraph

NAME = 0
RATE = 1
CEIL = 2
CHILDREN = 3


def create_leaf_node(env, node, parent):
    return htb.ShaperTokenBucket(
        env, node[NAME], node[RATE], node[CEIL], parent)


def create_inner_node(node, parent):
    return htb.TokenBucketNode(
        node[NAME], node[RATE], node[CEIL], parent)


def create_shaper_subtree(env, nodes, parent):
    shapers = []
    for node in nodes:
        if len(node[CHILDREN]) == 0:
            shapers.append(create_leaf_node(env, node, parent))
        else:
            inner_node = create_inner_node(node, parent)
            shapers += create_shaper_subtree(
                env, node[CHILDREN], inner_node)
    return shapers


def create_rate_limiter(env, profile, source, sink):
    shapers = []
    rl = htb.RateLimiter(env)

    root = create_inner_node(profile, None)
    shapers += create_shaper_subtree(env, profile[CHILDREN], root)

    for shaper in shapers:
        shaper.inp = source
        shaper.outp = sink
        rl.add_shaper(shaper)

    return rl


def simulate(name, profile):
    def const_size():
        return 100.0

    env = simpy.Environment()

    pg = htb.PacketGenerator("Source", const_size)
    ps = htb.PacketSink(env, 'Sink')

    rl = create_rate_limiter(env, profile, pg, ps)

    env.run(until=1000)

    print('[' + name + ']')
    rl.shapers.sort(key=lambda x: x.name)
    for shaper in rl.shapers:
        print(shaper.stats())
    print(ps.stats())
    print()

    render(name, rl.shapers)


def render(profile, shapers):
    def format_label(name, ceil, rate):
        return "%s|{C:%d|R:%d}" % (name, ceil, rate)

    g = Digraph(format='png')
    g.body.extend(['rankdir=BT'])
    g.attr('node', shape='record', style='rounded')

    inner_nodes = []
    for shaper in shapers:
        g.node(shaper.name,
               format_label(shaper.name, shaper.ceil, shaper.rate))

        parent = shaper.parent
        child = shaper
        edge_label = shaper.stats(short=True)
        while parent:
            if parent.name not in inner_nodes:
                inner_nodes.append(parent.name)
                g.node(parent.name,
                       format_label(parent.name, parent.ceil, parent.rate))
                g.edge(parent.name, child.name, edge_label)
                break

            g.edge(parent.name, child.name, edge_label)
            edge_label = ''
            child = parent
            parent = child.parent

    g.body.append('{ rank=same %s }' % (' '.join([x.name for x in shapers])))
    g.render('images/'+profile)


if __name__ == '__main__':
    profile1 = ('Root', 800, 800,
                [('S1', 300, 800, []), ('S2', 200, 800, [])])
    simulate("Profile1", profile1)

    profile2 = ('Root', 800, 800,
                [('S1', 200, 300, []), ('S2', 400, 500, [])])
    simulate("Profile2", profile2)

    profile3 = ('Root', 1000, 1000,
                [('S1', 150, 150, []),
                 ('S2', 150, 150, []),
                 ('S3', 150, 150, []),
                 ('S4', 150, 150, [])])
    simulate("Profile3", profile3)

    profile4 = ('Root', 10000, 10000,
                [('S1', 150, 150, []),
                 ('S2', 150, 150, []),
                 ('S3', 150, 150, []),
                 ('S4', 150, 150, []),
                 ('S5', 150, 150, []),
                 ('S6', 150, 150, []),
                 ('S7', 150, 2000, [])])
    simulate("Profile4", profile4)

    profile5 = ('Root', 1000, 1000,
                [('S1', 200, 300, []),
                 ('S2', 150, 150, []),
                 ('S3', 300, 400,
                  [('S3_1', 150, 250, []),
                   ('S3_2', 150, 200, [])]),
                 ('S4', 150, 150, [])])
    simulate("Profile5", profile5)



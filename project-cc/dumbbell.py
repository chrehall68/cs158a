#!/usr/bin/env python3
"""Dumbbell topology for the TCP congestion control project.

    snd0 --[delay d ]--+                                         +-- rcv0
                       |-- s1 ==[bottleneck: C, buffer B]== s2 --|
    snd1 --[delay d1]--+                                         +-- rcv1

Usage:
    sudo python3 dumbbell.py [--bw 50] [--delay 10ms] [--delay1 40ms]
                             [--buf 1] [--loss 0]

Addresses: snd<i> = 10.0.0.<1+i>, rcv<i> = 10.0.0.<101+i>
Bottleneck queue: s1-eth1 (s1 -> s2 direction)

Complete every TODO. Keep the command-line options, host names, and
addresses unchanged: the commands in the handout depend on them.
"""
import argparse
import os

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.topo import Topo

MTU = 1500  # bytes


class Dumbbell(Topo):
    def build(self, n=2, bw=50, delay='10ms', delay1=None, q=83, loss=0):
        """n:      number of sender/receiver pairs
           bw:     bottleneck capacity C in Mbps
           delay:  one-way delay d on each sender link (e.g. '10ms')
           delay1: one-way delay d1 for snd1 only (E3); None = same as delay
           q:      bottleneck buffer B in packets
           loss:   random loss on the bottleneck in percent (E5)"""
        s1, s2 = self.addSwitch('s1'), self.addSwitch('s2')

        # TODO 1: Add the bottleneck link between s1 and s2.
        #   - It must be the first link you add, so it gets s1-eth1/s2-eth1.
        #   - Rate limit both directions to bw, with a queue of q packets.
        #   - Do NOT put the propagation delay here (see the handout).
        #   - Apply loss only in the data direction (s1 -> s2).
        #   Hint: addLink() accepts params1=dict(...) and params2=dict(...)
        #   for the s1 side and the s2 side. TCLink understands bw (Mbps),
        #   delay, loss (percent), and max_queue_size (packets).
        #   Docs: params1/params2 in Link.__init__:
        #     http://mininet.org/api/classmininet_1_1link_1_1Link.html
        #   bw, delay, loss, max_queue_size in TCIntf.config:
        #     http://mininet.org/api/classmininet_1_1link_1_1TCIntf.html

        for i in range(n):
            snd = self.addHost(f'snd{i}', ip=f'10.0.0.{1 + i}/24')
            rcv = self.addHost(f'rcv{i}', ip=f'10.0.0.{101 + i}/24')

            # TODO 2: Connect snd to s1 and rcv to s2.
            #   - Put the propagation delay on the sender's link. TCLink
            #     applies it in each direction, so RTT_min = 2 * delay.
            #   - snd1 uses delay1 instead when delay1 is given.
            #   - Give the sender's link a large max_queue_size (e.g. 10000)
            #     so it never drops packets.
            #   - The receiver's link needs no parameters.


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bw', type=float, default=50,
                   help='bottleneck capacity C in Mbps (default 50)')
    p.add_argument('--delay', default='10ms',
                   help='one-way delay d on each sender link; RTT_min = 2d (default 10ms)')
    p.add_argument('--delay1', default=None,
                   help='one-way delay d1 for snd1 only, for E3 (default: same as --delay)')
    p.add_argument('--buf', type=float, default=1,
                   help='bottleneck buffer B in units of BDP (default 1)')
    p.add_argument('--loss', type=float, default=0,
                   help='random loss on the bottleneck in percent, for E5 (default 0)')
    a = p.parse_args()

    # TODO 3: Compute RTT_min (seconds), the BDP in packets, and the buffer
    # q = buf x BDP in packets (at least 1). Use snd0's delay (--delay).
    rtt = None
    bdp_pkts = None
    q = None
    print(f'*** RTT_min = {rtt * 1000:.0f} ms, BDP = {bdp_pkts:.0f} pkts, '
          f'B = {a.buf} x BDP = {q} pkts')

    topo = Dumbbell(bw=a.bw, delay=a.delay, delay1=a.delay1, q=q, loss=a.loss)
    # Standalone learning switches: no OpenFlow controller needed
    net = Mininet(topo=topo, link=TCLink, switch=OVSBridge, controller=None)
    net.start()

    # Clean cwnd traces: no TCP/Generic Segmentation Offload (TSO/GSO) or
    # Generic Receive Offload (GRO) anywhere, so the queue
    # limit counts real 1500 B packets rather than 64 KB super-packets
    for node in net.hosts + net.switches:
        for intf in node.intfNames():
            if intf != 'lo':
                node.cmd(f'ethtool -K {intf} tso off gso off gro off')

    for h in net.hosts:
        # Don't reuse cached ssthresh from the previous trial
        h.cmd('sysctl -w net.ipv4.tcp_no_metrics_save=1')
        if h.name.startswith('rcv'):
            h.cmd('iperf3 -s -D')

    CLI(net)

    os.system('pkill -f "iperf3 -s"')
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    main()

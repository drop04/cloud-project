import ipaddress, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_subnets_are_adjacent_and_big_enough():
    need = {"app": 1000, "public": 250, "data": 100, "management": 20}
    plan = {"app": "10.20.0.0/22", "public": "10.20.4.0/24", "data": "10.20.5.0/25", "management": "10.20.5.128/27"}
    prev_end = int(ipaddress.ip_address("10.20.0.0"))
    for name, cidr in plan.items():
        net = ipaddress.ip_network(cidr)
        assert int(net.network_address) == prev_end
        assert net.num_addresses - 2 >= need[name]
        assert (ipaddress.ip_network((int(net.network_address), net.prefixlen + 1)).num_addresses - 2) < need[name]
        prev_end = int(net.broadcast_address) + 1


def test_nacl_sample_packets():
    out = subprocess.run([sys.executable, "tools/nacl_sim.py", "network/nacl.json",
                          "network/packets_sample.jsonl", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0 and "100.0%" in out.stdout

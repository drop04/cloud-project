# Subnet allocation for 10.20.0.0/16

Rule: allocate largest → smallest, each block right after the previous one, using the
smallest prefix `p` with `2^(32-p) - 2 >= hosts needed`.

| Subnet | Hosts needed | Working | Prefix | Network | Usable range | Broadcast | Usable hosts |
|---|---|---|---|---|---|---|---|
| app | 1,000 | /23 → 510 (too few); /22 → 2^10−2 = **1,022** | /22 | 10.20.0.0 | 10.20.0.1 – 10.20.3.254 | 10.20.3.255 | 1,022 |
| public | 250 | /25 → 126 (too few); /24 → 2^8−2 = **254** | /24 | 10.20.4.0 | 10.20.4.1 – 10.20.4.254 | 10.20.4.255 | 254 |
| data | 100 | /26 → 62 (too few); /25 → 2^7−2 = **126** | /25 | 10.20.5.0 | 10.20.5.1 – 10.20.5.126 | 10.20.5.127 | 126 |
| management | 20 | /28 → 14 (too few); /27 → 2^5−2 = **30** | /27 | 10.20.5.128 | 10.20.5.129 – 10.20.5.158 | 10.20.5.159 | 30 |

## Placement
1. `app` starts at 10.20.0.0 and spans 1,024 addresses (10.20.0.0 – 10.20.3.255).
2. `public` starts at the next address, 10.20.4.0, and spans 256 (… 10.20.4.255).
3. `data` starts at 10.20.5.0 and spans 128 (… 10.20.5.127).
4. `management` starts at 10.20.5.128 and spans 32 (… 10.20.5.159).

Each block starts on a multiple of its own size, so no padding is needed. Verified by `tests/test_network.py`.

## NACL explanation (for `public` subnet)
A NACL is **stateless**: it does not remember that an outbound request was allowed, so it judges every packet
on its own. A client's request (e.g. to TCP 443) is covered by an inbound rule, but the reply leaves/arrives on
an ephemeral port (1024–65535) and is a *different packet* that needs its own rule: outbound TCP 1024–65535 to
clients, and inbound TCP 1024–65535 from the `app` subnet for the replies of the load balancer's calls to port 8000.

Rules are evaluated from the lowest number upward and the **first match wins**. The deny for `198.51.100.0/24`
is rule 100, below the allows for ports 80/443 (110/120). If the deny had a higher number, a packet from that
range to port 443 would match the allow rule first and be let in, so the deny would never take effect.

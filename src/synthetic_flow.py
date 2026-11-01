from __future__ import annotations

import random
import secrets


PROTOCOLS = ("tcp", "udp", "icmp", "arp", "ospf", "sctp")
TCP_SERVICES = (
    "-",
    "http",
    "ftp",
    "ftp-data",
    "smtp",
    "ssh",
    "pop3",
    "ssl",
    "irc",
)
UDP_SERVICES = ("-", "dns", "dhcp", "snmp", "radius")
TCP_STATES = ("FIN", "CON", "INT", "REQ", "RST")
OTHER_STATES = ("INT", "CON", "REQ", "RST", "no")


def generate_synthetic_flow(rng: random.Random | None = None) -> dict[str, int | float | str]:
    """Create a new plausible flow from explicit bounds, without reading datasets."""
    generator = rng or random.Random(secrets.randbits(64))
    proto = generator.choice(PROTOCOLS)
    service = generator.choice(TCP_SERVICES if proto == "tcp" else UDP_SERVICES)
    if proto not in {"tcp", "udp"}:
        service = "-"
    state = generator.choice(TCP_STATES if proto == "tcp" else OTHER_STATES)

    duration = round(generator.uniform(0.001, 60.0), 6)
    source_packets = generator.randint(1, 200)
    destination_packets = generator.randint(0, 200)
    source_mean = generator.randint(40, 1500)
    destination_mean = generator.randint(40, 1500) if destination_packets else 0
    source_bytes = source_packets * source_mean
    destination_bytes = destination_packets * destination_mean
    source_interval = duration / (source_packets - 1) if source_packets > 1 else 0.0
    destination_interval = (
        duration / (destination_packets - 1) if destination_packets > 1 else 0.0
    )

    is_tcp = proto == "tcp"
    is_ftp = service in {"ftp", "ftp-data"} and generator.random() < 0.25
    is_http = service == "http"
    ftp_commands = generator.randint(1, 8) if is_ftp else 0
    http_methods = generator.randint(1, 8) if is_http else 0
    synack = generator.uniform(0.0001, 0.5) if is_tcp else 0.0
    ackdat = generator.uniform(0.0001, 0.5) if is_tcp else 0.0

    return {
        "dur": duration,
        "proto": proto,
        "service": service,
        "state": state,
        "spkts": source_packets,
        "dpkts": destination_packets,
        "sbytes": source_bytes,
        "dbytes": destination_bytes,
        "rate": round((source_packets + destination_packets) / duration, 6),
        "sttl": generator.randint(1, 255),
        "dttl": generator.randint(1, 255) if destination_packets else 0,
        "sload": round(source_bytes * 8 / duration, 6),
        "dload": round(destination_bytes * 8 / duration, 6),
        "sloss": generator.randint(0, min(source_packets, 5)),
        "dloss": generator.randint(0, min(destination_packets, 5)),
        "sinpkt": round(source_interval * generator.uniform(0.75, 1.25), 6),
        "dinpkt": round(destination_interval * generator.uniform(0.75, 1.25), 6),
        "sjit": round(source_interval * generator.random(), 6),
        "djit": round(destination_interval * generator.random(), 6),
        "swin": generator.randint(0, 65535) if is_tcp else 0,
        "stcpb": generator.randint(0, 2**32 - 1) if is_tcp else 0,
        "dtcpb": generator.randint(0, 2**32 - 1) if is_tcp else 0,
        "dwin": generator.randint(0, 65535) if is_tcp and destination_packets else 0,
        "tcprtt": round(synack + ackdat, 6),
        "synack": round(synack, 6),
        "ackdat": round(ackdat, 6),
        "smean": source_mean,
        "dmean": destination_mean,
        "trans_depth": generator.randint(1, 8) if is_http else 0,
        "response_body_len": generator.randint(0, 65536) if is_http else 0,
        "ct_srv_src": generator.randint(1, 50),
        "ct_state_ttl": generator.randint(0, 20),
        "ct_dst_ltm": generator.randint(1, 50),
        "ct_src_dport_ltm": generator.randint(1, 50),
        "ct_dst_sport_ltm": generator.randint(1, 50),
        "ct_dst_src_ltm": generator.randint(1, 50),
        "is_ftp_login": int(is_ftp),
        "ct_ftp_cmd": ftp_commands,
        "ct_flw_http_mthd": http_methods,
        "ct_src_ltm": generator.randint(1, 50),
        "ct_srv_dst": generator.randint(1, 50),
        "is_sm_ips_ports": generator.randint(0, 1),
    }

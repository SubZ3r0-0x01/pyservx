#!/usr/bin/env python3
"""WebRTC signaling relay for PyServeX P2P fallback transfers.

Peers that cannot reach the server directly (symmetric NAT / firewall)
exchange SDP offers/answers + ICE candidates through this lightweight
HTTP polling relay, then stream file bytes directly peer-to-peer via an
RTCDataChannel using Google's public STUN server for NAT discovery.

HTTP API:
  POST /webrtc/signal   {room, from, type: join|offer|answer|candidate|leave, data}
  GET  /webrtc/poll?room=R&since=N&peer=P -> {messages:[...], index:N}
Rooms auto-expire after 10 minutes of inactivity.

Hardening (mirrors FileSync's signaling limits):
  * hard caps on rooms / peers-per-room / per-message payload size
  * per-peer-per-room message rate limit
  * ICE relay-candidate private addresses rewritten to the sender's
    server-observed address so symmetric-NAT peers can establish a path
  * bounded message history; stale peers dropped on TTL
"""

import ipaddress
import threading
import time

ROOM_TTL = 600            # seconds without activity before a room is purged
MAX_ROOMS = 500           # soft-danger: refuse to create rooms beyond this
MAX_PEERS_PER_ROOM = 64   # refuse joins beyond this
MAX_MESSAGES = 200        # per-room history kept for late pollers
MAX_MSG_BYTES = 32 * 1024 # reject signaling payloads larger than this
MSG_RATE_LIMIT = 60       # max messages per (room, peer) window
MSG_RATE_WINDOW = 60.0    # seconds
PEER_ID_MAX = 64


class SignalingError(Exception):
    """Carries an HTTP status for the route handler."""
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def _rewrite_relay_candidate(cand_str, client_host):
    """Rewrite private addresses in an ICE candidate line to the client's
    server-observed address. Public addresses are left untouched."""
    if not client_host or not cand_str or "typ" not in cand_str:
        return cand_str
    parts = cand_str.split()
    # candidate strings are whitespace separated; the transport address is
    # at fixed offsets (foundation, component, proto, priority, ip, port, ...)
    if not (parts and parts[0].startswith("candidate:") and len(parts) >= 6):
        return cand_str
    addr, port = parts[4], parts[5]
    try:
        if not ipaddress.ip_address(addr).is_private:
            return cand_str
    except ValueError:
        return cand_str
    parts[4] = client_host
    return " ".join(parts)


class SignalingHub:
    def __init__(self):
        self.lock = threading.RLock()
        # room -> {"messages":[...], "peers":{peer: ts}, "counts":{peer:[ts,...]}, "last": ts}
        self.rooms = {}

    def _get_room(self, room):
        with self.lock:
            if room not in self.rooms:
                if len(self.rooms) >= MAX_ROOMS:
                    raise SignalingError("signaling capacity reached", 503)
                self.rooms[room] = {"messages": [], "peers": {},
                                    "counts": {}, "last": time.time()}
            return self.rooms[room]

    def post(self, room, sender, mtype, data, client_host=None):
        """Store a signaling message on a room bus. Returns its seq number."""
        if room is None or len(room) > 64 or not room.strip():
            raise SignalingError("invalid room id")
        if sender is None or len(sender) > PEER_ID_MAX or not sender.strip():
            raise SignalingError("invalid peer id")

        with self.lock:
            r = self._get_room(room)
            now = time.time()
            # per-peer rate limit
            window = [t for t in r["counts"].get(sender, []) if now - t < MSG_RATE_WINDOW]
            if len(window) >= MSG_RATE_LIMIT:
                raise SignalingError("signaling rate limit reached", 429)
            window.append(now)
            r["counts"][sender] = window[-MSG_RATE_LIMIT:]

            if mtype == "join":
                if sender in r["peers"]:
                    r["peers"][sender] = now
                elif len(r["peers"]) >= MAX_PEERS_PER_ROOM:
                    raise SignalingError("room is full", 503)
                else:
                    r["peers"][sender] = now
            elif mtype == "leave":
                r["peers"].pop(sender, None)

            payload = data
            if mtype == "candidate" and isinstance(payload, dict):
                cand = payload.get("candidate")
                if isinstance(cand, str):
                    payload = dict(payload)
                    payload["candidate"] = _rewrite_relay_candidate(
                        cand, client_host)

            if len(str(payload)) > MAX_MSG_BYTES:
                raise SignalingError("signaling payload too large", 413)

            r["last"] = now
            seq = len(r["messages"]) + 1
            msg = {"seq": seq, "ts": now, "peer": sender,
                   "type": mtype, "data": payload}
            r["messages"].append(msg)
            del r["messages"][:-MAX_MESSAGES]
            return seq

    def poll(self, room, since=0, exclude_peer=None):
        with self.lock:
            r = self.rooms.get(room)
            if not r:
                return [], 0
            try:
                since = int(since)
            except (TypeError, ValueError):
                since = 0
            msgs = [m for m in r["messages"]
                    if m["seq"] > since and m["peer"] != exclude_peer]
            return msgs, len(r["messages"])

    def peers(self, room):
        with self.lock:
            r = self.rooms.get(room)
            return list(r["peers"].keys()) if r else []

    def cleanup_loop(self, stop_event):
        while not stop_event.wait(120):
            cutoff = time.time() - ROOM_TTL
            with self.lock:
                dead = [rm for rm, r in self.rooms.items() if r["last"] < cutoff]
                for rm in dead:
                    del self.rooms[rm]


STUN_SERVERS = [
    "stun:stun.l.google.com:19302",
    "stun:stun1.l.google.com:19302",
]
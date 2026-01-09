import struct
import json
import zlib

# OpCodes
REQ_LOGIN = 0x01
RESP_LOGIN = 0x02
REQ_JOIN = 0x03
RESP_ROOM = 0x04
ROOM_LIST = 0x05
REQ_LEAVE = 0x06
NOTIFY = 0x07
DATA = 0x08
REQ_LIST_ROOMS = 0x09

# P2P OpCodes
REQ_P2P_INIT = 0x0A       # Client A -> Server: I want to chat with B
REQ_P2P_START = 0x0B      # Server -> Client B: Open a port for A
RESP_P2P_READY = 0x0C     # Client B -> Server: I'm listening on Port X
RESP_P2P_CONNECT = 0x0D   # Server -> Client A: Connect to B on IP:Port

PING = 0xFD
PONG = 0xFE
ERROR = 0xFF

# Error Codes
ERR_FULL = 0x01
ERR_AUTH = 0x02
ERR_GAME = 0x03
ERR_UNKNOWN = 0xFF

HEADER_SIZE = 4

def pack_message(opcode, payload=b''):
    """
    Packs a message: [Size (4 bytes)] + [OpCode (1 byte)] + [Payload]
    Size = 1 (OpCode) + len(Payload)
    """
    if isinstance(payload, str):
        payload = payload.encode('utf-8')
    elif isinstance(payload, dict) or isinstance(payload, list):
        payload = json.dumps(payload).encode('utf-8')

    msg_len = 1 + len(payload) # OpCode + Payload
    header = struct.pack('!I', msg_len) # Big-Endian Unsigned Int
    
    return header + struct.pack('B', opcode) + payload

def unpack_header(data):
    """
    Unpacks the header to get the message size.
    Expects 4 bytes.
    Returns size (int).
    """
    if len(data) != 4:
        raise ValueError("Header must be 4 bytes")
    return struct.unpack('!I', data)[0]

def parse_packet(data):
    """
    Parses a full packet body (excluding size header).
    Data should be [OpCode (1)] + [Payload]
    Returns (opcode, payload)
    """
    if not data:
        raise ValueError("Empty data")
    
    opcode = data[0]
    payload = data[1:]
    return opcode, payload

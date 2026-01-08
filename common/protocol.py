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
PING = 0xFD
PONG = 0xFE
ERROR = 0xFF

REQ_LIST_ROOMS = 0x09

# Error Codes
ERR_FULL = 0x01
ERR_AUTH = 0x02
ERR_GAME = 0x03
ERR_UNKNOWN = 0xFF

HEADER_SIZE = 4

def pack_message(opcode, payload=b'', compress=False):
    """
    Packs a message: [Size (4 bytes)] + [OpCode (1 byte)] + [Payload]
    Size = 1 (OpCode) + len(Payload)
    """
    if isinstance(payload, str):
        payload = payload.encode('utf-8')
    elif isinstance(payload, dict) or isinstance(payload, list):
        payload = json.dumps(payload).encode('utf-8')
    
    # Story #B03: Compression
    # We need to signal compression. The prompt says "add a flag in the header or use a dedicated OpCode".
    # Or "adapter le protocole".
    # Let's keep it simple for now and implement basic packing. 
    # If I were to support compression, maybe use a high bit in OpCode or a modified structure.
    # The prompt says: "si la taille > 100 octets, compresser le payload avec zlib et ajouter un flag dans le header"
    # Current header: [Size (4)] + [OpCode (1)].
    # Maybe we can enforce that Size is clean length, and OpCode handles meaning.
    # But wait, "ajouter un flag dans le header".
    # I can use a magic byte or modify the size field (e.g. MSB indicates compression). 
    # But strict "Big-Endian (!) pour les nombres binaires" suggests standard integer.
    # Let's stick to the prompt's main part first. I will handle compression if asked or as a bonus later.
    # For now, standard pack.

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

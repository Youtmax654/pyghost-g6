import unittest
import struct
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common import protocol

class TestProtocol(unittest.TestCase):
    def test_pack_simple(self):
        opcode = protocol.REQ_LOGIN
        payload = b"TestUser"
        packed = protocol.pack_message(opcode, payload)
        
        # Check total length
        # Size (4) + OpCode (1) + Payload (8) = 13 bytes
        expected_len = 1 + len(payload)
        self.assertEqual(len(packed), 4 + expected_len)
        
        # Check header
        size_unpacked = struct.unpack('!I', packed[:4])[0]
        self.assertEqual(size_unpacked, expected_len)
        
        # Check OpCode
        self.assertEqual(packed[4], opcode)
        
        # Check Payload
        self.assertEqual(packed[5:], payload)

    def test_unpack_header(self):
        data = struct.pack('!I', 42)
        size = protocol.unpack_header(data)
        self.assertEqual(size, 42)

    def test_parse_packet(self):
        opcode = protocol.DATA
        payload = b'{"type":"GAME_START"}'
        data = struct.pack('B', opcode) + payload
        
        op, py = protocol.parse_packet(data)
        self.assertEqual(op, opcode)
        self.assertEqual(py, payload)

    def test_pack_utf8_string(self):
        # pack_message handles strings by encoding them
        opcode = protocol.REQ_LOGIN
        payload = "Héllo"
        packed = protocol.pack_message(opcode, payload)
        
        expected_payload = payload.encode('utf-8')
        self.assertEqual(packed[5:], expected_payload)
        
    def test_pack_json_dict(self):
        opcode = protocol.DATA
        payload = {"foo": "bar"}
        packed = protocol.pack_message(opcode, payload)
        
        # Should be json dumped and encoded
        expected_payload = b'{"foo": "bar"}' # Default separators may vary, but let's check
        # json.dumps defaults to (', ', ': ')
        # Let's decode to check semantic equality
        op, res_payload = protocol.parse_packet(packed[4:])
        import json
        decoded = json.loads(res_payload.decode('utf-8'))
        self.assertEqual(decoded, payload)

if __name__ == '__main__':
    unittest.main()

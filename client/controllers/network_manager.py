import socket
import threading
import sys
import os
import json
import time
import struct

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from common import protocol

class NetworkManager(threading.Thread):
    def __init__(self, host='127.0.0.1', port=5000):
        super().__init__()
        self.host = host
        self.port = port
        self.sock = None
        self.running = False
        self.pseudo = None
        self.room_list_cb = None
        
        # Callbacks
        self.on_connect = None
        self.on_disconnect = None
        self.on_error = None
        self.on_login_response = None
        self.on_room_list = None
        self.on_room_response = None # Join success
        self.on_game_data = None
        self.on_notify = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.running = True
            self.start()
            if self.on_connect: self.on_connect()
            return True
        except Exception as e:
            if self.on_error: self.on_error(f"Connection failed: {e}")
            return False

    def run(self):
        while self.running:
            try:
                # Read Header
                header = self._recv_all(protocol.HEADER_SIZE)
                if not header: break
                
                size = protocol.unpack_header(header)
                body = self._recv_all(size)
                if not body: break
                
                opcode, payload = protocol.parse_packet(body)
                self.process_packet(opcode, payload)
                
            except Exception as e:
                print(f"Network Loop Error: {e}")
                break
        
        self.disconnect()

    def _recv_all(self, n):
        data = b''
        while len(data) < n:
            try:
                chunk = self.sock.recv(n - len(data))
                if not chunk: return None
                data += chunk
            except:
                return None
        return data

    def send_request(self, opcode, payload=b''):
        if not self.sock: return
        try:
            msg = protocol.pack_message(opcode, payload)
            self.sock.sendall(msg)
        except Exception as e:
            print(f"Send Error: {e}")
            self.disconnect()

    def process_packet(self, opcode, payload):
        if opcode == protocol.RESP_LOGIN:
            status = payload[0]
            if self.on_login_response: self.on_login_response(status == 0)
            
        elif opcode == protocol.RESP_ROOM:
            # Payload: [NbPlayer(1)] + [Len][Pseudo]...
            count = payload[0]
            offset = 1
            players = []
            try:
                for _ in range(count):
                    plen = payload[offset]
                    offset += 1
                    p_str = payload[offset:offset+plen].decode('utf-8')
                    players.append(p_str)
                    offset += plen
                if self.on_room_response: self.on_room_response(players)
            except:
                pass

        elif opcode == protocol.ROOM_LIST:
            # Payload: [NbRooms(4)] + Loop...
            # ID(4), NameLen(1), Name, P(1), M(1)
            try:
                nb_rooms = struct.unpack('!I', payload[:4])[0]
                offset = 4
                rooms = []
                for _ in range(nb_rooms):
                    rid = struct.unpack('!I', payload[offset:offset+4])[0]
                    offset += 4
                    nlen = payload[offset]
                    offset += 1
                    rname = payload[offset:offset+nlen].decode('utf-8')
                    offset += nlen
                    rplayers = payload[offset]
                    offset += 1
                    rmax = payload[offset]
                    offset += 1
                    
                    rooms.append({"id": rid, "name": rname, "players": rplayers, "max": rmax})
                
                if self.on_room_list: self.on_room_list(rooms)
            except Exception as e:
                print(f"Room List Parse Error: {e}")

        elif opcode == protocol.DATA:
            try:
                data = json.loads(payload.decode('utf-8'))
                if self.on_game_data: self.on_game_data(data)
            except Exception as e:
                print(f"DEBUG: Data handling error: {e}")
                pass

        elif opcode == protocol.NOTIFY:
            # [Type] + [Pseudo]
            ntype = payload[0]
            pseudo = payload[1:].decode('utf-8')
            if self.on_notify: self.on_notify(ntype, pseudo)

        elif opcode == protocol.PING:
            self.send_request(protocol.PONG)

        elif opcode == protocol.ERROR:
            try:
                msg = payload.decode('utf-8')
            except:
                msg = "Unknown Error"
            if self.on_error: self.on_error(msg)

    def login(self, pseudo):
        self.pseudo = pseudo
        self.send_request(protocol.REQ_LOGIN, pseudo)

    def fetch_room_list(self):
        self.send_request(protocol.REQ_LIST_ROOMS)

    def join_room(self, room_id):
        self.send_request(protocol.REQ_JOIN, int(room_id).to_bytes(4, 'big'))
        
    def leave_room(self):
        self.send_request(protocol.REQ_LEAVE)

    def send_game_data(self, data_dict):
        self.send_request(protocol.DATA, data_dict)
    
    def disconnect(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except: pass
        if self.on_disconnect: self.on_disconnect()

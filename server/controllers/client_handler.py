import threading
import socket
import time
import json
import struct
from common import protocol, utils

logger = utils.setup_logger("ClientHandler")

class ClientHandler(threading.Thread):
    def __init__(self, sock, addr, server):
        super().__init__()
        self.sock = sock
        self.addr = addr
        self.server = server # Reference to main server object (for RoomManager, Client List)
        self.pseudo = None
        self.running = True
        self.current_room = None
        self.last_packet = time.time()
        # Heartbeat state
        self.last_ping_sent = time.time()
        self.waiting_pong = False
        self.pong_deadline = 0
        
    def run(self):
        logger.info(f"New connection from {self.addr}")
        self.sock.settimeout(1.0) # Non-blocking with timeout to allow checking 'running'

        while self.running:
            try:
                # Read Header
                header_data = self._recv_all(4)
                if not header_data:
                    break # Connection closed
                
                size = protocol.unpack_header(header_data)
                
                # Check max size (safety) - e.g. 10MB
                if size > 10 * 1024 * 1024:
                    logger.warning(f"Packet too large from {self.addr}")
                    break

                # Read Body (size bytes)
                # Note: protocol.pack_message sets size = 1 (opcode) + len(payload)
                # So we read size bytes.
                body_data = self._recv_all(size)
                if not body_data:
                    break
                
                opcode, payload = protocol.parse_packet(body_data)
                self.last_packet = time.time()
                
                self.handle_check_heartbeat_response(opcode)
                self.process_packet(opcode, payload)
                
            except socket.timeout:
                self.check_heartbeat_cycle()
                continue
            except Exception as e:
                logger.error(f"Error handling client {self.addr}: {e}")
                break
        
        self.disconnect()

    def _recv_all(self, n):
        data = b''
        while len(data) < n:
            try:
                chunk = self.sock.recv(n - len(data))
                if not chunk:
                    return None
                data += chunk
            except socket.timeout:
                self.check_heartbeat_cycle()
                if not self.running: return None
                continue
            except OSError:
                return None
        return data

    def send_raw(self, data):
        try:
            self.sock.sendall(data)
        except Exception:
            self.running = False

    def send_message(self, opcode, payload=b''):
        # Story #B03: Compression Logic could go here (if > 100 bytes)
        # For now, simple pack.
        msg = protocol.pack_message(opcode, payload)
        self.send_raw(msg)

    def process_packet(self, opcode, payload):
        if opcode == protocol.REQ_LOGIN:
            self.handle_login(payload)
        elif opcode == protocol.REQ_JOIN:
            self.handle_join(payload)
        elif opcode == protocol.REQ_LEAVE:
            self.handle_leave()
        elif opcode == protocol.DATA:
            self.handle_game_data(payload)
        elif opcode == protocol.REQ_LIST_ROOMS:
            self.handle_list_rooms()
        elif opcode == protocol.PONG:
            pass # Handled in loop/heartbeat logic
        else:
            logger.warning(f"Unknown opcode {opcode} from {self.pseudo or self.addr}")

    def handle_login(self, payload):
        try:
            requested_pseudo = payload.decode('utf-8')
        except:
            self.send_message(protocol.ERROR, b"Invalid encoding")
            return

        if self.server.is_pseudo_taken(requested_pseudo):
            self.send_message(protocol.RESP_LOGIN, b'\x01') # Refused
        else:
            self.pseudo = requested_pseudo
            self.server.register_client(self)
            self.send_message(protocol.RESP_LOGIN, b'\x00') # OK
            # Bonus sequence: Send Room List immediately? Usually client asks.

    def handle_join(self, payload):
        if not self.pseudo:
            self.send_message(protocol.ERROR, b"Login first")
            return
        
        if len(payload) != 4:
            return
        
        room_id = int.from_bytes(payload, 'big')
        room = self.server.room_manager.get_room(room_id)
        
        if room:
            if room.add_client(self):
                self.current_room = room
                # Notify room members
                # 0x07 NOTIFY: [Type(0=JOIN)] + [Pseudo]
                notif = b'\x00' + self.pseudo.encode('utf-8')
                room.broadcast(protocol.pack_message(protocol.NOTIFY, notif), exclude=self)
                
                # Send RESP_ROOM: [NbPlayers] + [Pseudos...]
                # This seems complex to pack as per prompt "Liste Pseudos..." implies variable list.
                # Just separate by null or length? Prompt is vague on List format.
                # "NbPlayers(1 byte) + Liste Pseudos...". 
                # I'll concatenate them with a delimiter or length-prefixed strings. 
                # Given UTF-8, maybe null terminated or size-prefixed.
                # Let's use simple JSON for list usually, but prompt says "Liste Pseudos..." (binary?).
                # Let's assume just concatenated C-strings (null terminated) or Length+String.
                # Let's use: for each player: [Len(1)] + [String].
                
                resp_payload = bytes([len(room.clients)])
                for c in room.clients:
                    p_bytes = c.pseudo.encode('utf-8')
                    # If strictly adhering to "Liste Pseudos...", maybe just concatenated?
                    # Let's do: [Len(1)] + [Bytes] for safety.
                    # Or check valid spec? "NbPlayers(1) + Liste Pseudos".
                    # I'll stick to encoding pseudos as strings with a delimiter?
                    # Let's do: [Len(1)][Pseudo]. safely.
                    resp_payload += bytes([len(p_bytes)]) + p_bytes

                self.send_message(protocol.RESP_ROOM, resp_payload)
            else:
                self.send_message(protocol.ERROR, b"Room full")
        else:
            self.send_message(protocol.ERROR, b"Room not found")

    def handle_leave(self):
        if self.current_room:
            # Notify others
            notif = b'\x01' + self.pseudo.encode('utf-8') # 1=LEAVE
            self.current_room.broadcast(protocol.pack_message(protocol.NOTIFY, notif), exclude=self)
            self.current_room.remove_client(self)
            self.current_room = None

    def handle_list_rooms(self):
        # [NbRooms(4)] + loop: [ID(4)] + [NameLen(1)] + [Name] + [Players(1)] + [Max(1)]
        rooms = self.server.room_manager.list_rooms()
        payload = struct.pack('!I', len(rooms))
        
        for r in rooms:
            rid = r['id']
            rname = r['name'].encode('utf-8')
            rplayers = r['players']
            rmax = r['max']
            
            payload += struct.pack('!I', rid)
            payload += struct.pack('B', len(rname))
            payload += rname
            payload += struct.pack('B', rplayers)
            payload += struct.pack('B', rmax)
        
        self.send_message(protocol.ROOM_LIST, payload)

    def handle_game_data(self, payload):
        # Relay to room + Game Logic
        if not self.current_room:
            return

        # Decode JSON
        try:
            data = json.loads(payload.decode('utf-8'))
        except:
            return

        msg_type = data.get("type")
        game = self.current_room.game_state
        
        # Verify Turn (Story #06)
        # Except CHAT? Prompt says "Letter" via DATA.
        # Story #05: "Messages de jeu (lettres) sont envoyés via OpCode DATA".
        
        # If play letter:
        if msg_type == "PLAY_LETTER":
            if game.get_current_player() != self.pseudo:
                self.send_message(protocol.ERROR, b"Not your turn")
                return
            
            letter = data.get("letter")
            res = game.play_letter(letter)
            
            # Broadcast update
            # Build GAME_STATE
            state = {
                "type": "GAME_STATE",
                "frag": game.frag,
                "scores": game.scores,
                "active_player": game.get_current_player() # Need to switch turn first?
            }
            
            if res == "LOSE_WORD":
                # Current player loses
                punish = game.punish_player(self.pseudo)
                state["scores"] = game.scores # Update scores
                state["frag"] = game.frag 
                state["event"] = f"{self.pseudo} completed a valid word!"
                if punish == "ELIMINATED":
                     game.remove_player(self.pseudo)
                     # Handle elimination logic
            
            if res == "CONTINUE":
                game.next_turn()
            
            state["active_player"] = game.get_current_player()
            self._broadcast_room_json(state)

        elif msg_type == "CHALLENGE":
             # Check turn? Usually you challenge OUT of turn immediately after play?
             # Or only active player can challenge previous?
             # Rule 3: "Un joueur peut Challenger le précédent..."
             # Usually in Ghost, you challenge when it's your turn, instead of playing a letter.
             if game.get_current_player() != self.pseudo:
                 self.send_message(protocol.ERROR, b"Not your turn to challenge")
                 return
             
             previous = game.players[(game.players.index(self.pseudo) - 1) % len(game.players)]
             res = game.challenge()
             
             if res == "PREVIOUS_LOSES":
                 game.punish_player(previous)
                 msg = f"Challenge successful! {previous} loses."
             else:
                 game.punish_player(self.pseudo)
                 msg = f"Challenge failed! {self.pseudo} loses."
            
             # Reset round logic implicitly handled by punish_player resetting frag?
             # Punish player resets frag.
             
             state = {
                "type": "GAME_STATE",
                "frag": game.frag,
                "scores": game.scores,
                "active_player": game.get_current_player(),
                "event": msg
             }
             self._broadcast_room_json(state)
             
        elif msg_type == "CHAT":
            # Just relay
             self._broadcast_room_json(data) # Assume data has sender/msg

    def _broadcast_room_json(self, data_dict):
        if self.current_room:
            payload = json.dumps(data_dict).encode('utf-8')
            msg = protocol.pack_message(protocol.DATA, payload)
            self.current_room.broadcast(msg)

    def handle_check_heartbeat_response(self, opcode):
        if opcode == protocol.PONG:
            self.waiting_pong = False
            # Reset timer, wait another 30s
            self.last_ping_sent = time.time()

    def check_heartbeat_cycle(self):
        now = time.time()
        if self.waiting_pong:
            if now > self.pong_deadline:
                logger.warning(f"Client {self.pseudo} timed out (Heartbeat)")
                self.running = False
        else:
            if now - self.last_ping_sent > 30:
                self.send_message(protocol.PING)
                self.waiting_pong = True
                self.pong_deadline = now + 5

    def disconnect(self):
        self.running = False
        self.handle_leave()
        if self.pseudo:
            self.server.unregister_client(self)
        try:
            self.sock.close()
        except:
            pass

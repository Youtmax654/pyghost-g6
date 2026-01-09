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
        elif opcode == protocol.REQ_P2P_INIT:
            self.handle_p2p_init(payload)
        elif opcode == protocol.RESP_P2P_READY:
            self.handle_p2p_ready(payload)
        elif opcode == protocol.PONG:
            pass # Handled in loop/heartbeat logic
        else:
            logger.warning(f"Unknown opcode {opcode} from {self.pseudo or self.addr}")

    def handle_p2p_init(self, payload):
        # Client A wants to chat with B
        try:
            target_pseudo = payload.decode('utf-8')
        except:
            return

        target = None
        for c in self.server.clients:
            if c.pseudo == target_pseudo:
                target = c
                break
        
        if not target:
            self.send_message(protocol.ERROR, b"Utilisateur introuvable")
            return

        if target == self:
            self.send_message(protocol.ERROR, b"Impossible de P2P avec soi-meme")
            return
            
        # Send REQ_P2P_START to Target
        # Payload: [RequesterPseudo]
        logger.info(f"P2P Init: {self.pseudo} -> {target_pseudo}")
        target.send_message(protocol.REQ_P2P_START, self.pseudo.encode('utf-8'))

    def handle_p2p_ready(self, payload):
        # Client B is ready and listening. Payload: [RequesterPseudoLen][RequesterPseudo][Port]
        # We need to forward IP:Port to Requester.
        try:
            req_len = payload[0]
            req_pseudo = payload[1:1+req_len].decode('utf-8')
            port_bytes = payload[1+req_len:1+req_len+4]
            port = int.from_bytes(port_bytes, 'big')
        except Exception as e:
            logger.error(f"P2P Ready Parse Error: {e}")
            return

        requester = None
        for c in self.server.clients:
            if c.pseudo == req_pseudo:
                requester = c
                break
        
        if not requester:
            return # Requester gone?

        # Send RESP_P2P_CONNECT to Requester
        # Payload: [IPLen][IP][Port]
        # self.addr is (IP, Port), we need IP.
        target_ip = self.addr[0]
        # Loopback issue: if target_ip is 127.0.0.1 and we are on same machine it works.
        # If real network, it should be the public IP seen by server.
        
        ip_bytes = target_ip.encode('utf-8')
        resp_payload = struct.pack('B', len(ip_bytes)) + ip_bytes + struct.pack('!I', port)
        
        logger.info(f"P2P Connect: {requester.pseudo} connecting to {self.pseudo} at {target_ip}:{port}")
        requester.send_message(protocol.RESP_P2P_CONNECT, resp_payload)

    def handle_login(self, payload):
        try:
            requested_pseudo = payload.decode('utf-8')
        except:
            self.send_message(protocol.ERROR, b"Encodage invalide")
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
            self.send_message(protocol.ERROR, b"Connectez-vous d'abord")
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

                # Broadcast initial game state so everyone sees "Waiting..." or current state
                game = room.game_state
                
                active = "En attente..."
                if len(room.clients) >= 2:
                    active = game.get_current_player()
                
                state = {
                    "type": "GAME_STATE",
                    "frag": game.frag,
                    "scores": game.scores,
                    "active_player": active
                }
                self._broadcast_room_json(state)
            else:
                self.send_message(protocol.ERROR, b"Salle pleine")
        else:
            self.send_message(protocol.ERROR, b"Salle introuvable")

    def handle_leave(self):
        if self.current_room:
            # Notify others
            notif = b'\x01' + self.pseudo.encode('utf-8') # 1=LEAVE
            self.current_room.broadcast(protocol.pack_message(protocol.NOTIFY, notif), exclude=self)
            self.current_room.remove_client(self)
            
            # Broadcast update if room still active
            if self.current_room and len(self.current_room.clients) > 0:
                game = self.current_room.game_state
                
                # Check if we should revert to waiting
                active = "En attente..."
                if len(self.current_room.clients) >= 2:
                     active = game.get_current_player()

                state = {
                    "type": "GAME_STATE",
                    "frag": game.frag,
                    "scores": game.scores,
                    "active_player": active
                }
                # We need to broadcast from an existing client handler context or use room broadcast
                # Since 'self' is leaving, we can use room.broadcast with JSON payload
                payload = json.dumps(state).encode('utf-8')
                msg = protocol.pack_message(protocol.DATA, payload)
                self.current_room.broadcast(msg)

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
        
        # If play letter:
        if msg_type == "PLAY_LETTER":
            if game.get_current_player() != self.pseudo:
                self.send_message(protocol.ERROR, b"Ce n'est pas votre tour")
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
                # Current player loses because they completed a word
                punish = game.punish_player(self.pseudo)
                
                # WORD COMPLETED -> RESET
                game.frag = ""

                state["event"] = f"{self.pseudo} a complete un mot valide !"
                if punish == "ELIMINATED":
                     # game.remove_player(self.pseudo) <-- Don't just remove, end game for all
                     game_over_msg = {
                         "type": "GAME_OVER",
                         "reason": f"{self.pseudo} a atteint GHOST en premier !"
                     }
                     # Update scores one last time before ending
                     state["scores"] = game.scores
                     self._broadcast_room_json(state)
                     self._broadcast_room_json(game_over_msg)
                     
                     # Server-side cleanup should arguably happen when they leave
                     # But we can also force clear the game state if needed
                     # For now, rely on clients leaving.
                     return
                
                game.next_turn()

            elif res == "LOSE_INVALID":
                # Current player loses because fragment is invalid
                punish = game.punish_player(self.pseudo)
                
                # INVALID LETTER -> REVERT ONLY LAST CHAR (Continue word)
                if len(game.frag) > 0:
                    game.frag = game.frag[:-1]
                
                state["event"] = f"{self.pseudo} a joue une lettre invalide (mot impossible) !"
                if punish == "ELIMINATED":
                    # game.remove_player(self.pseudo)
                    game_over_msg = {
                         "type": "GAME_OVER",
                         "reason": f"{self.pseudo} a atteint GHOST en premier !"
                    }
                    state["scores"] = game.scores
                    self._broadcast_room_json(state)
                    self._broadcast_room_json(game_over_msg)
                    return         
                
                game.next_turn()
            
            elif res == "CONTINUE":
                game.next_turn()
            
            # Update state with final corrections
            state["scores"] = game.scores
            state["frag"] = game.frag
            state["active_player"] = game.get_current_player()
            self._broadcast_room_json(state)

        elif msg_type == "CHAT":
            # Just relay
             self._broadcast_room_json(data) # Assume data has sender/msg

    def _broadcast_room_json(self, data_dict):
        if self.current_room:
            logger.info(f"DEBUG_SERVER: Broadcasting: {data_dict} to {self.current_room.name}")
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

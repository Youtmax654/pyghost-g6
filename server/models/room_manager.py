from .game_state import GameState
from common import utils

logger = utils.setup_logger("RoomManager")

class Room:
    def __init__(self, room_id, name):
        self.id = room_id
        self.name = name
        self.clients = [] # List of ClientHandler
        self.game_state = GameState()
        self.max_players = 5

    def add_client(self, client):
        if len(self.clients) >= self.max_players:
            return False
        self.clients.append(client)
        self.game_state.add_player(client.pseudo)
        return True

    def remove_client(self, client):
        if client in self.clients:
            self.clients.remove(client)
            self.game_state.remove_player(client.pseudo)
            return True
        return False

    def broadcast(self, message, exclude=None):
        for client in self.clients:
            if client != exclude:
                try:
                    client.send_raw(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast to {client.pseudo}: {e}")

class RoomManager:
    def __init__(self):
        self.rooms = {}
        # Pre-create rooms (Story #03)
        self.create_room(1, "Table 1")
        self.create_room(2, "Table 2")
        self.create_room(3, "Table 3")

    def create_room(self, room_id, name):
        self.rooms[room_id] = Room(room_id, name)
        logger.info(f"Room created: {name} (ID: {room_id})")

    def get_room(self, room_id):
        return self.rooms.get(room_id)
    
    def list_rooms(self):
        # Returns list of dict info
        res = []
        for r in self.rooms.values():
            res.append({
                "id": r.id,
                "name": r.name,
                "players": len(r.clients),
                "max": r.max_players
            })
        return res

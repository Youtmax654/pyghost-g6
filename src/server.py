"""
PyGhost TCP Server
Handles client connections, login, and room management.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from protocol import (
    OpCode, encode_message, decode_header, decode_packet,
    decode_login_req, encode_login_resp, encode_room_list,
    decode_join_req, encode_room_resp, encode_notify, RoomInfo
)


@dataclass
class Room:
    """Represents a game room."""
    room_id: int
    name: str
    max_players: int
    players: Set[str] = field(default_factory=set)
    
    @property
    def player_count(self) -> int:
        return len(self.players)
    
    @property
    def is_full(self) -> bool:
        return self.player_count >= self.max_players
    
    def to_room_info(self) -> RoomInfo:
        return RoomInfo(
            room_id=self.room_id,
            name=self.name,
            players=self.player_count,
            max_players=self.max_players
        )


class ClientSession:
    """Represents a connected client."""
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.pseudo: Optional[str] = None
        self.current_room: Optional[Room] = None
        self.addr = writer.get_extra_info('peername')
    
    async def send(self, opcode: int, payload: bytes = b''):
        """Send a message to this client."""
        msg = encode_message(opcode, payload)
        self.writer.write(msg)
        await self.writer.drain()


class GhostServer:
    """Async TCP server for PyGhost."""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 5555):
        self.host = host
        self.port = port
        self.clients: Dict[str, ClientSession] = {}  # pseudo -> session
        self.rooms: Dict[int, Room] = {}  # room_id -> room
        self.server: Optional[asyncio.Server] = None
        
        # Create hardcoded rooms
        self._create_rooms()
    
    def _create_rooms(self):
        """Create hardcoded rooms."""
        rooms_data = [
            (1, "Room Alpha", 4),
            (2, "Room Beta", 4),
            (3, "Room Gamma", 2),
        ]
        for room_id, name, max_players in rooms_data:
            self.rooms[room_id] = Room(room_id, name, max_players)
        print(f"Created {len(self.rooms)} rooms")
    
    async def start(self):
        """Start the server."""
        self.server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        print(f"Server listening on {self.host}:{self.port}")
        async with self.server:
            await self.server.serve_forever()
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a new client connection."""
        session = ClientSession(reader, writer)
        print(f"Client connected: {session.addr}")
        
        try:
            while True:
                # Read header (4 bytes)
                header = await reader.readexactly(4)
                msg_size = decode_header(header)
                
                # Read body
                body = await reader.readexactly(msg_size)
                opcode, payload = decode_packet(body)
                
                await self._handle_message(session, opcode, payload)
                
        except asyncio.IncompleteReadError:
            print(f"Client disconnected: {session.addr}")
        except Exception as e:
            print(f"Error with client {session.addr}: {e}")
        finally:
            # Cleanup
            await self._cleanup_session(session)
            writer.close()
            await writer.wait_closed()
    
    async def _cleanup_session(self, session: ClientSession):
        """Clean up when a client disconnects."""
        # Remove from room
        if session.current_room and session.pseudo:
            room = session.current_room
            room.players.discard(session.pseudo)
            # Notify others
            for pseudo in room.players:
                if pseudo in self.clients:
                    await self.clients[pseudo].send(
                        OpCode.NOTIFY, 
                        encode_notify(0x01, session.pseudo)  # LEAVE
                    )
        
        # Remove from clients
        if session.pseudo and session.pseudo in self.clients:
            del self.clients[session.pseudo]
    
    async def _handle_message(self, session: ClientSession, opcode: int, payload: bytes):
        """Process a received message."""
        if opcode == OpCode.REQ_LOGIN:
            await self._handle_login(session, payload)
        elif opcode == OpCode.REQ_JOIN:
            await self._handle_join(session, payload)
        elif opcode == OpCode.REQ_LEAVE:
            await self._handle_leave(session)
        elif opcode == OpCode.PONG:
            pass  # Heartbeat response, ignore
        else:
            print(f"Unknown opcode from {session.addr}: {opcode}")
    
    async def _handle_login(self, session: ClientSession, payload: bytes):
        """Handle login request."""
        pseudo = decode_login_req(payload)
        print(f"Login request from {session.addr}: '{pseudo}'")
        
        # Validate pseudo
        if not pseudo or len(pseudo) > 20 or pseudo in self.clients:
            await session.send(OpCode.RESP_LOGIN, encode_login_resp(0x01))
            print(f"Login refused for '{pseudo}'")
            return
        
        # Accept login
        session.pseudo = pseudo
        self.clients[pseudo] = session
        
        await session.send(OpCode.RESP_LOGIN, encode_login_resp(0x00))
        print(f"Login accepted for '{pseudo}'")
        
        # Send room list
        await self._send_room_list(session)
    
    async def _send_room_list(self, session: ClientSession):
        """Send the list of rooms to a client."""
        room_infos = [room.to_room_info() for room in self.rooms.values()]
        await session.send(OpCode.ROOM_LIST, encode_room_list(room_infos))
    
    async def _handle_join(self, session: ClientSession, payload: bytes):
        """Handle join room request."""
        room_id = decode_join_req(payload)
        print(f"Join request from {session.pseudo}: room {room_id}")
        
        room = self.rooms.get(room_id)
        if not room or room.is_full or not session.pseudo:
            # Could send ERROR, but for now just ignore
            print(f"Join refused for room {room_id}")
            return
        
        # Leave current room if any
        if session.current_room:
            await self._leave_room(session)
        
        # Join new room
        room.players.add(session.pseudo)
        session.current_room = room
        
        # Send RESP_ROOM with player list
        players = list(room.players)
        await session.send(OpCode.RESP_ROOM, encode_room_resp(players))
        print(f"{session.pseudo} joined room '{room.name}'")
        
        # Notify others in room
        for pseudo in room.players:
            if pseudo != session.pseudo and pseudo in self.clients:
                await self.clients[pseudo].send(
                    OpCode.NOTIFY,
                    encode_notify(0x00, session.pseudo)  # JOIN
                )
    
    async def _handle_leave(self, session: ClientSession):
        """Handle leave room request."""
        await self._leave_room(session)
        # Send updated room list
        await self._send_room_list(session)
    
    async def _leave_room(self, session: ClientSession):
        """Remove a session from its current room."""
        if session.current_room and session.pseudo:
            room = session.current_room
            room.players.discard(session.pseudo)
            
            # Notify others
            for pseudo in room.players:
                if pseudo in self.clients:
                    await self.clients[pseudo].send(
                        OpCode.NOTIFY,
                        encode_notify(0x01, session.pseudo)  # LEAVE
                    )
            
            session.current_room = None


async def main():
    server = GhostServer()
    await server.start()


if __name__ == '__main__':
    asyncio.run(main())

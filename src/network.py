"""
Network layer for PyGhost client.
Handles async TCP communication with the server.
"""
import asyncio
import threading
from enum import IntEnum
from typing import Callable, Optional, List, Tuple
from protocol import (
    OpCode, encode_message, decode_header, decode_packet,
    encode_login_req, decode_login_resp, decode_room_list, 
    encode_join_req, decode_room_resp, decode_notify, RoomInfo
)


class LoginStatus(IntEnum):
    OK = 0x00
    REFUSED = 0x01


class NotifyType(IntEnum):
    JOIN = 0x00
    LEAVE = 0x01


class NetworkClient:
    """Async network client for PyGhost."""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 5555):
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.on_login_response: Optional[Callable[[LoginStatus], None]] = None
        self.on_room_list: Optional[Callable[[List[RoomInfo]], None]] = None
        self.on_room_joined: Optional[Callable[[List[str]], None]] = None
        self.on_notify: Optional[Callable[[NotifyType, str], None]] = None
        self.on_disconnected: Optional[Callable[[], None]] = None
    
    def start(self):
        """Start the network thread."""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
    
    def _run_loop(self):
        """Run the asyncio event loop in a separate thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_and_listen())
    
    async def _connect_and_listen(self):
        """Connect to server and listen for messages."""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            print(f"Connected to {self.host}:{self.port}")
            
            # Listen loop
            while True:
                header = await self.reader.readexactly(4)
                msg_size = decode_header(header)
                body = await self.reader.readexactly(msg_size)
                opcode, payload = decode_packet(body)
                
                self._handle_message(opcode, payload)
                
        except asyncio.IncompleteReadError:
            print("Disconnected from server")
            if self.on_disconnected:
                self.on_disconnected()
        except Exception as e:
            print(f"Network error: {e}")
            if self.on_disconnected:
                self.on_disconnected()
    
    def _handle_message(self, opcode: int, payload: bytes):
        """Process received message."""
        if opcode == OpCode.RESP_LOGIN:
            status = LoginStatus(decode_login_resp(payload))
            if self.on_login_response:
                self.on_login_response(status)
        elif opcode == OpCode.ROOM_LIST:
            rooms = decode_room_list(payload)
            if self.on_room_list:
                self.on_room_list(rooms)
        elif opcode == OpCode.RESP_ROOM:
            players = decode_room_resp(payload)
            if self.on_room_joined:
                self.on_room_joined(players)
        elif opcode == OpCode.NOTIFY:
            notify_type, pseudo = decode_notify(payload)
            if self.on_notify:
                self.on_notify(NotifyType(notify_type), pseudo)
        elif opcode == OpCode.PING:
            self._send_sync(OpCode.PONG, b'')
    
    def _send_sync(self, opcode: int, payload: bytes):
        """Send a message synchronously from the network thread."""
        if self.writer and self._loop:
            msg = encode_message(opcode, payload)
            asyncio.run_coroutine_threadsafe(
                self._async_send(msg), self._loop
            )
    
    async def _async_send(self, msg: bytes):
        """Send raw bytes."""
        if self.writer:
            self.writer.write(msg)
            await self.writer.drain()
    
    def login(self, pseudo: str):
        """Send login request."""
        payload = encode_login_req(pseudo)
        self._send_sync(OpCode.REQ_LOGIN, payload)
    
    def join_room(self, room_id: int):
        """Send join room request."""
        payload = encode_join_req(room_id)
        self._send_sync(OpCode.REQ_JOIN, payload)
    
    def close(self):
        """Close the connection."""
        if self.writer:
            self.writer.close()

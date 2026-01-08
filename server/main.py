import socket
import threading
import sys
import os
import flet as ft
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common import utils, protocol
from server.controllers.client_handler import ClientHandler
from server.models.room_manager import RoomManager
from server.views.admin_dashboard import AdminDashboard

HOST = '0.0.0.0'
PORT = 5000

logger = utils.setup_logger("GhostServer")

class GhostServer:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = [] # List of ClientHandler
        self.room_manager = RoomManager()
        self.running = True

    def start(self):
        try:
            self.server_socket.bind((HOST, PORT))
            self.server_socket.listen(5)
            logger.info(f"Server started on {HOST}:{PORT}")
        except Exception as e:
            logger.error(f"Failed to bind: {e}")
            sys.exit(1)

        # Accept thread
        accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        accept_thread.start()
        
        # Start Admin Dashboard (Main Thread)
        dashboard = AdminDashboard(self)
        ft.run(dashboard.main)

    def _accept_loop(self):
        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                
                # Story #B01: Load Balancer simplified logic
                # "Si plus de 5 clients sont connectés, refuse... et redirige"
                if len(self.clients) >= 5: # Limit for test
                    logger.info(f"Server full, rejecting {addr}")
                    # Send specific error or redirect (Not fully spec'd how to redirect protocol-wise efficiently without custom opcode or just ERROR msg)
                    # "redirige ... via un message ERROR ... vers un serveur secondaire"
                    # Sending ERROR 0xFF + "REDIRECT:5001"
                    try:
                        err_msg = protocol.pack_message(protocol.ERROR, b"FULL: Redirect to 5001")
                        client_sock.sendall(err_msg)
                        client_sock.close()
                    except:
                        pass
                    continue
                
                handler = ClientHandler(client_sock, addr, self)
                handler.start()
            except Exception as e:
                logger.error(f"Accept error: {e}")

    def register_client(self, handler):
        self.clients.append(handler)
        logger.info(f"Client registered: {handler.pseudo}")

    def unregister_client(self, handler):
        if handler in self.clients:
            self.clients.remove(handler)
            logger.info(f"Client unregistered: {handler.pseudo}")

    def is_pseudo_taken(self, pseudo):
        for c in self.clients:
            if c.pseudo == pseudo:
                return True
        return False

    def get_all_clients(self):
        return list(self.clients)

    def broadcast_admin_message(self, text):
        # Broadcast to all clients (in rooms or lobby?)
        # Story #11 says "global à tous les clients".
        # We send a DATA message with sender="ADMIN".
        import json
        payload = {
            "type": "BROADCAST",
            "sender": "ADMIN",
            "message": text
        }
        msg = protocol.pack_message(protocol.DATA, payload)
        for c in self.clients:
            try:
                c.send_raw(msg)
            except:
                pass

if __name__ == "__main__":
    server = GhostServer()
    server.start()

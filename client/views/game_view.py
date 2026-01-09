import flet as ft
from client.controllers.network_manager import NetworkManager
import time
import queue
import asyncio
import threading

class GameClientApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Client Jeu Ghost"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window_width = 600
        self.page.window_height = 800
        self.page.padding = 20
        
        self.network = NetworkManager()
        
        # State
        self.current_pseudo = ""
        self.current_room = None
        self.players_in_room = []
        self.game_state = {}
        
        self.event_queue = queue.Queue()
        
        # UI Components
        self.main_container = ft.Column(expand=True)
        self.page.add(self.main_container)

        self.login_view = None
        self.lobby_view = None
        self.room_view = None
        
        # Global UI elements
        self.broadcast_content = ft.Text("")
        self.broadcast_dialog = ft.AlertDialog(
            title=ft.Text("Admin Broadcast"),
            content=self.broadcast_content,
            actions=[
                ft.TextButton("OK", on_click=self.close_broadcast_dialog)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        
        self.page.dialog = self.broadcast_dialog
        
        self.setup_callbacks()
        self.setup_p2p_callbacks()
        self.show_connection_screen()

    def setup_callbacks(self):
        # We redirect all network callbacks to the queue
        self.network.on_connect = lambda: self.event_queue.put(("CONNECT", None))
        self.network.on_error = lambda msg: self.event_queue.put(("ERROR", msg))
        self.network.on_login_response = lambda s: self.event_queue.put(("LOGIN_RESP", s))
        self.network.on_room_list = lambda r: self.event_queue.put(("ROOM_LIST", r))
        self.network.on_room_response = lambda p: self.event_queue.put(("JOIN_ROOM", p))
        self.network.on_game_data = lambda d: self.event_queue.put(("GAME_DATA", d))
        self.network.on_notify = lambda t, p: self.event_queue.put(("NOTIFY", (t, p)))
        self.network.on_disconnect = lambda: self.event_queue.put(("DISCONNECT", None))
        
        # Don't connect yet

    async def run_async_loop(self):
        while True:
            try:
                # Process all pending events
                while not self.event_queue.empty():
                    evt_type, data = self.event_queue.get_nowait()
                    self.process_event(evt_type, data)
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Erreur de boucle: {e}")
                await asyncio.sleep(0.1)

    def process_event(self, evt_type, data):
        if evt_type == "CONNECT":
            print("Connecté")
        elif evt_type == "ERROR":
            self.show_error(data)
        elif evt_type == "LOGIN_RESP":
            success = data
            if success:
                self.show_lobby()
                self.network.fetch_room_list()
            else:
                self.show_error("Pseudo refusé")
        elif evt_type == "ROOM_LIST":
            self.update_room_list(data)
        elif evt_type == "JOIN_ROOM":
            self.players_in_room = data
            self.show_game_room()
        elif evt_type == "GAME_DATA":
            self.handle_game_data(data)
        elif evt_type == "NOTIFY":
            ntype, pseudo = data
            self.handle_notify(ntype, pseudo)
        elif evt_type == "DISCONNECT":
            self.show_error("Déconnecté")
        elif evt_type == "P2P_REQ":
            self.handle_p2p_request(data)
        elif evt_type == "P2P_START":
            sock, peer = data
            self.handle_p2p_start(sock, peer)
            
        self.page.update()

    def show_error(self, msg):
        snack = ft.SnackBar(ft.Text(f"Erreur: {msg}", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED)
        self.page.overlay.append(snack)
        snack.open = True
        self.page.update()

    def show_info(self, msg):
        snack = ft.SnackBar(ft.Text(str(msg), color=ft.Colors.WHITE), bgcolor=ft.Colors.BLUE)
        self.page.overlay.append(snack)
        snack.open = True
        self.page.update()

    # --- VIEWS ---

    def show_connection_screen(self):
        self.ip_input = ft.TextField(label="IP Serveur", value="127.0.0.1", width=200, on_submit=self.do_connect_and_login)
        self.port_input = ft.TextField(label="Port", value="5000", width=100, on_submit=self.do_connect_and_login)
        self.pseudo_input = ft.TextField(label="Pseudo", autofocus=True, width=200, on_submit=self.do_connect_and_login)
        
        join_btn = ft.ElevatedButton("Se connecter et Jouer", on_click=self.do_connect_and_login, width=200)
        
        content = ft.Column([
            ft.Text("JEU GHOST", size=40, weight="bold", color=ft.Colors.BLUE_200),
            ft.Text("Jeu de mots multijoueur", size=16, color=ft.Colors.GREY_400),
            ft.Container(height=50),
            ft.Row([self.ip_input, self.port_input], alignment=ft.MainAxisAlignment.CENTER),
            self.pseudo_input,
            ft.Container(height=20),
            join_btn
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        
        self.main_container.controls = [content]
        self.main_container.update()

    def do_connect_and_login(self, e):
        ip = self.ip_input.value
        port_str = self.port_input.value
        pseudo = self.pseudo_input.value
        
        if not ip or not port_str or not pseudo:
            self.show_error("Tous les champs sont requis")
            return
            
        try:
            port = int(port_str)
        except:
            self.show_error("Port Invalide")
            return

        self.current_pseudo = pseudo
        
        # Configure Network
        self.network.host = ip
        self.network.port = port
        
        # Connect
        if self.network.connect():
            # If successful, try login
            self.network.login(pseudo)
        else:
            self.show_error("Impossible de se connecter au serveur")

    def show_lobby(self):
        self.room_list_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        refresh_btn = ft.IconButton(ft.Icons.REFRESH, on_click=lambda e: self.network.fetch_room_list())
        
        self.main_container.controls = [
            ft.Row([ft.Text("Salon", size=25), refresh_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            self.room_list_col
        ]
        self.main_container.update()
    
    def update_room_list(self, rooms):
        self.room_list_col.controls.clear()
        for r in rooms:
            btn = ft.ElevatedButton(
                "Rejoindre", 
                on_click=lambda e, rid=r['id']: self.network.join_room(rid),
                disabled=(r['players'] >= r['max'])
            )
            card = ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(r['name'], weight="bold"),
                        ft.Text(f"Joueurs: {r['players']}/{r['max']}", size=12)
                    ]),
                    btn
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=10,
                border=ft.border.all(1, ft.Colors.GREY_800),
                border_radius=10,
                bgcolor=ft.Colors.GREY_900
            )
            self.room_list_col.controls.append(card)
        self.room_list_col.update()

    def show_game_room(self):
        # Header
        # Header
        self.lbl_room_info = ft.Text(f"Salle: {len(self.players_in_room)} Joueurs", size=16)
        is_full = len(self.players_in_room) >= 2
        self.leave_btn = ft.IconButton(
            ft.Icons.EXIT_TO_APP, 
            on_click=self.do_leave_room,
            disabled=is_full
        )
        if is_full:
            self.show_info("Salle pleine ! Le jeu commence.")
        
        # Game Board
        self.word_display = ft.Text("", size=40, weight="bold", color=ft.Colors.GREEN_400, text_align="center")
        self.status_display = ft.Text("En attente...", size=14, color=ft.Colors.GREY)
        
        # Controls
        self.input_letter = ft.TextField(label="Lettre", width=100, max_length=1, disabled=True, on_submit=self.do_play_letter)
        self.btn_play = ft.ElevatedButton("Jouer", on_click=self.do_play_letter, disabled=True)
        self.game_container = ft.Column([
            ft.Container(height=20),
            ft.Text("Les mots à deviner sont en français uniquement !", size=12),
            self.word_display,
            ft.Container(height=20),
            self.status_display,
            ft.Container(height=30),
            ft.Row([self.input_letter, self.btn_play], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=10),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        # Chat / Log
        self.chat_list = ft.ListView(expand=True, spacing=5, auto_scroll=True)
        self.chat_input = ft.TextField(hint_text="Tchat...", expand=True, on_submit=self.do_send_chat)
        
        self.main_container.controls = [
            ft.Row([self.lbl_room_info, self.leave_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            self.game_container,
            ft.Divider(),
            ft.Container(self.chat_list, height=200, border=ft.border.all(1, ft.Colors.GREY_800)),
            ft.Row([self.chat_input, ft.IconButton(ft.Icons.SEND, on_click=self.do_send_chat)]),
            ft.Divider(),
            ft.Row([
                ft.Text("Chat Privé :", size=12),
                ft.TextField(label="Autre Pseudo", width=150, on_submit=lambda e: self.do_p2p_request(e.control.value)),
                ft.IconButton(ft.Icons.CONNECT_WITHOUT_CONTACT, on_click=lambda e: self.do_p2p_request(e.control.parent.controls[1].value))
            ])
        ]
        self.main_container.update()

    def do_leave_room(self, e):
        self.network.leave_room()
        self.show_lobby()
        self.network.fetch_room_list()

    def do_play_letter(self, e):
        let = self.input_letter.value
        if let and len(let) == 1:
            self.network.send_game_data({"type": "PLAY_LETTER", "letter": let})
            self.input_letter.value = ""
            self.input_letter.update()

    # Challenge Removed

    def do_send_chat(self, e):
        msg = self.chat_input.value
        if msg:
            self.network.send_game_data({"type": "CHAT", "sender": self.current_pseudo, "message": msg})
            self.chat_input.value = ""
            self.chat_input.update()

    def do_p2p_request(self, target_pseudo):
        if target_pseudo and target_pseudo != self.current_pseudo:
            self.network.request_p2p(target_pseudo)
            self.show_info(f"Demande envoyée à {target_pseudo}")

    def handle_game_data(self, data):
        dtype = data.get("type")
        
        if dtype == "GAME_STATE":
            self.word_display.value = data.get("frag", "")
            active = data.get("active_player")
            event = data.get("event", "")
            
            scores = data.get("scores", {})
            score_txt = "Scores: " + ", ".join([f"{k}: {v}" for k, v in scores.items()])
            
            status = f"Tour : {active}\n{score_txt}"
            if event:
                self.add_log(f"Jeu : {event}")
            
            self.status_display.value = status
            self.word_display.update()
            
            # BLOCK/UNBLOCK INPUT based on turn
            is_my_turn = (active == self.current_pseudo)
            self.input_letter.disabled = not is_my_turn
            self.btn_play.disabled = not is_my_turn
            self.input_letter.update()
            self.btn_play.update()
            
            self.status_display.update()
            
        elif dtype == "CHAT":
            sender = data.get("sender", "?")
            msg = data.get("message", "")
            self.add_log(f"{sender}: {msg}")
            
        elif dtype == "BROADCAST":
            msg = data.get("message", "")
            full_msg = f"Admin a envoyé un message : {msg}"
            self.show_broadcast_modal(full_msg)
            
        elif dtype == "GAME_OVER":
            reason = data.get("reason", "Fin de partie")
            self.show_info(f"Fin de partie : {reason}")
            # Redirect to lobby after a short delay or immediately
            # We can use a dialog or just switch
            self.do_leave_room(None)

    def handle_notify(self, ntype, pseudo):
        # 0=JOIN, 1=LEAVE
        msg = f"{pseudo} a rejoint." if ntype == 0 else f"{pseudo} est parti."
        self.add_log(msg)
        if ntype == 0:
            if pseudo not in self.players_in_room: self.players_in_room.append(pseudo)
        else:
            if pseudo in self.players_in_room: self.players_in_room.remove(pseudo)
        
        if self.lbl_room_info:
            self.lbl_room_info.value = f"Salle: {len(self.players_in_room)} Joueurs"
            self.lbl_room_info.update()
        
        if hasattr(self, 'leave_btn') and self.leave_btn:
            is_full = len(self.players_in_room) >= 2
            self.leave_btn.disabled = is_full
            self.leave_btn.update()
            if is_full:
                 self.show_info("Salle pleine ! Le jeu commence.")

    def add_log(self, text):
        if self.chat_list:
            self.chat_list.controls.append(ft.Text(text, size=12))
            self.chat_list.update()

    def show_broadcast_modal(self, msg):
        self.broadcast_content.value = msg
        self.page.overlay.append(self.broadcast_dialog)
        self.broadcast_dialog.open = True
        self.page.update()

    def close_broadcast_dialog(self, e):
        self.broadcast_dialog.open = False
        self.page.update()

    # --- P2P UI ---

    def setup_p2p_callbacks(self):
        # Called in init
        self.network.on_p2p_incoming_request = lambda req: self.event_queue.put(("P2P_REQ", req))
        self.network.on_p2p_socket_ready = lambda s, p: self.event_queue.put(("P2P_START", (s, p)))

    def handle_p2p_request(self, requester):
        # Dialog to accept/refuse
        self.incoming_p2p_requester = requester
        
        def on_accept(e):
            self.network.accept_p2p_request(self.incoming_p2p_requester)
            self.p2p_confirm_dialog.open = False
            self.page.update()
            
        def on_refuse(e):
            self.p2p_confirm_dialog.open = False
            self.page.update()
            
        self.p2p_confirm_dialog = ft.AlertDialog(
            title=ft.Text("Demande de Chat Privé"),
            content=ft.Text(f"{requester} veut démarrer un chat privé avec vous."),
            actions=[
                ft.TextButton("Accepter", on_click=on_accept),
                ft.TextButton("Refuser", on_click=on_refuse)
            ]
        )
        self.page.overlay.append(self.p2p_confirm_dialog)
        self.p2p_confirm_dialog.open = True
        self.page.update()

    def handle_p2p_start(self, sock, peer):
        # Start the chat window
        print(f"Starting P2P with {peer}")
        chat_window = P2PChatWindow(sock, peer, self.current_pseudo)
        self.page.overlay.append(chat_window.build())
        chat_window.open()
        self.page.update()
        
        # Start reading from socket in background (managed by P2PChatWindow)
        threading.Thread(target=chat_window.read_loop, daemon=True).start()

class P2PChatWindow:
    def __init__(self, sock, peer_name, my_name):
        self.sock = sock
        self.peer = peer_name
        self.me = my_name
        self.dialog = None
        self.chat_list = ft.ListView(expand=True, spacing=5, auto_scroll=True, height=300)
        self.input = ft.TextField(hint_text="Message privé...", expand=True, on_submit=self.send_msg)

    def build(self):
        self.dialog = ft.AlertDialog(
            title=ft.Text(f"Chat Privé avec {self.peer}"),
            content=ft.Column([
                ft.Container(self.chat_list, border=ft.border.all(1, ft.Colors.GREY), height=300),
                ft.Row([self.input, ft.IconButton(ft.Icons.SEND, on_click=self.send_msg)])
            ], width=400, height=400),
            actions=[ft.TextButton("Fermer", on_click=self.close)]
        )
        return self.dialog

    def open(self):
        self.dialog.open = True

    def close(self, e):
        self.dialog.open = False
        try:
            self.sock.close()
        except: pass
        self.dialog.update()

    def send_msg(self, e):
        msg = self.input.value
        if msg:
            try:
                # Simple line protocol for P2P
                data = msg.encode('utf-8')
                self.sock.sendall(data)
                self.add_log(f"{self.me}: {msg}", color="blue")
                self.input.value = ""
                self.input.update()
            except Exception as ex:
                self.add_log(f"Error: {ex}", color="red")

    def read_loop(self):
        print("P2P Read Loop Started")
        while True:
            try:
                data = self.sock.recv(1024)
                if not data: break
                msg = data.decode('utf-8')
                print(f"P2P Recv: {msg}")
                self.add_log(f"{self.peer}: {msg}", color="green")
            except Exception as e:
                print(f"P2P Read Error: {e}")
                break
        self.add_log("Connexion fermée.", color="red")

    def add_log(self, text, color="white"):
        self.chat_list.controls.append(ft.Text(text, color=color))
        self.dialog.update()

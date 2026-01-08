import flet as ft
from client.controllers.network_manager import NetworkManager
import time

class GameClientApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Ghost Game Client"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window_width = 400
        self.page.window_height = 700
        self.page.padding = 20
        
        self.network = NetworkManager()
        self.setup_callbacks()
        
        # State
        self.current_pseudo = ""
        self.current_room = None
        self.players_in_room = []
        self.game_state = {}
        
        # UI Components
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
        
        self.show_login()

    def setup_callbacks(self):
        self.network.on_connect = lambda: print("Connected")
        self.network.on_error = self.show_error
        self.network.on_login_response = self.on_login_response
        self.network.on_room_list = self.on_room_list
        self.network.on_room_response = self.on_join_room_success
        self.network.on_game_data = self.on_game_data
        self.network.on_notify = self.on_notify
        self.network.on_disconnect = lambda: self.show_error("Disconnected from server")
        
        self.network.connect() # Auto connect on start

    def show_error(self, msg):
        snack = ft.SnackBar(ft.Text(f"Error: {msg}", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED)
        self.page.overlay.append(snack)
        snack.open = True
        self.page.update()

    # --- VIEWS ---

    def show_login(self):
        
        self.pseudo_input = ft.TextField(label="Choose Pseudo", autofocus=True)
        join_btn = ft.ElevatedButton("Enter Game", on_click=self.do_login, width=200)
        
        container = ft.Column([
            ft.Text("GHOST GAME", size=40, weight="bold", color=ft.Colors.BLUE_200),
            ft.Text("Multiplayer Word Game", size=16, color=ft.Colors.GREY_400),
            ft.Container(height=50),
            self.pseudo_input,
            ft.Container(height=20),
            join_btn
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        
        self.page.controls = [container]
        self.page.update()

    def do_login(self, e):
        pseudo = self.pseudo_input.value
        if not pseudo:
            self.show_error("Pseudo required")
            return
        self.network.login(pseudo)
        self.current_pseudo = pseudo

    def on_login_response(self, success):
        if success:
            self.show_lobby()
            self.network.fetch_room_list()
        else:
            self.show_error("Pseudo refused (already taken?)")

    def show_lobby(self):
        
        self.room_list_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        refresh_btn = ft.IconButton(ft.Icons.REFRESH, on_click=lambda e: self.network.fetch_room_list())
        
        self.page.controls = [
            ft.Row([ft.Text("Lobby", size=25), refresh_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            self.room_list_col
        ]
        self.page.update()
    
    def on_room_list(self, rooms):
        self.room_list_col.controls.clear()
        for r in rooms:
            # Card for each room
            btn = ft.ElevatedButton(
                "Join", 
                on_click=lambda e, rid=r['id']: self.network.join_room(rid),
                disabled=(r['players'] >= r['max'])
            )
            
            card = ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(r['name'], weight="bold"),
                        ft.Text(f"Players: {r['players']}/{r['max']}", size=12)
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

    def on_join_room_success(self, players):
        self.players_in_room = players
        self.show_game_room()

    def show_game_room(self):
        
        # Header
        self.lbl_room_info = ft.Text(f"Room: {len(self.players_in_room)} Players", size=16)
        leave_btn = ft.IconButton(ft.Icons.EXIT_TO_APP, on_click=self.do_leave_room)
        
        # Game Board
        self.word_display = ft.Text("", size=40, weight="bold", color=ft.Colors.GREEN_400, text_align="center")
        self.status_display = ft.Text("Waiting...", size=14, color=ft.Colors.GREY)
        
        # Controls
        self.input_letter = ft.TextField(label="Letter", width=100, max_length=1)
        self.btn_play = ft.ElevatedButton("Play", on_click=self.do_play_letter)
        self.btn_challenge = ft.ElevatedButton("Challenge!", on_click=self.do_challenge, bgcolor=ft.Colors.RED_900)
        
        self.game_container = ft.Column([
            ft.Container(height=20),
            ft.Text("Current Fragment:", size=12),
            self.word_display,
            ft.Container(height=20),
            self.status_display,
            ft.Container(height=30),
            ft.Row([self.input_letter, self.btn_play], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=10),
            self.btn_challenge
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        # Chat / Log
        self.chat_list = ft.ListView(expand=True, spacing=5, auto_scroll=True)
        self.chat_input = ft.TextField(hint_text="Chat...", expand=True, on_submit=self.do_send_chat)
        
        self.page.controls = [
            ft.Row([self.lbl_room_info, leave_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            self.game_container,
            ft.Divider(),
            ft.Container(self.chat_list, height=200, border=ft.border.all(1, ft.Colors.GREY_800)),
            ft.Row([self.chat_input, ft.IconButton(ft.Icons.SEND, on_click=self.do_send_chat)])
        ]
        self.page.update()

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

    def do_challenge(self, e):
        self.network.send_game_data({"type": "CHALLENGE"})

    def do_send_chat(self, e):
        msg = self.chat_input.value
        if msg:
            self.network.send_game_data({"type": "CHAT", "sender": self.current_pseudo, "message": msg})
            self.chat_input.value = ""
            self.chat_input.update()

    def on_game_data(self, data):
        dtype = data.get("type")
        
        if dtype == "GAME_STATE":
            self.word_display.value = data.get("frag", "")
            active = data.get("active_player")
            event = data.get("event", "")
            
            scores = data.get("scores", {})
            score_txt = "Scores: " + ", ".join([f"{k}: {v}" for k, v in scores.items()])
            
            status = f"Turn: {active}\n{score_txt}"
            if event:
                self.add_log(f"Game: {event}")
            
            self.status_display.value = status
            self.word_display.update()
            self.status_display.update()
            
        elif dtype == "CHAT":
            sender = data.get("sender", "?")
            msg = data.get("message", "")
            self.add_log(f"{sender}: {msg}")
            
        elif dtype == "BROADCAST":
            msg = data.get("message", "")
            self.show_broadcast_modal(msg)

    def on_notify(self, ntype, pseudo):
        # 0=JOIN, 1=LEAVE
        msg = f"{pseudo} joined." if ntype == 0 else f"{pseudo} left."
        self.add_log(msg)
        if ntype == 0:
            if pseudo not in self.players_in_room: self.players_in_room.append(pseudo)
        else:
            if pseudo in self.players_in_room: self.players_in_room.remove(pseudo)
        
        if self.lbl_room_info:
            self.lbl_room_info.value = f"Room: {len(self.players_in_room)} Players"
            self.lbl_room_info.update()

    def add_log(self, text):
        if self.chat_list:
            self.chat_list.controls.append(ft.Text(text, size=12))
            self.chat_list.update()

    def show_broadcast_modal(self, msg):
        print(f"DEBUG: Showing broadcast modal: {msg}")
        self.broadcast_content.value = msg
        # self.broadcast_content.update() # REMOVED: Cannot update control not currently displayed
        self.broadcast_dialog.open = True
        self.page.update()

    def close_broadcast_dialog(self, e):
        self.broadcast_dialog.open = False
        self.page.update()


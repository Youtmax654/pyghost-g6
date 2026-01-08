import flet as ft
import threading
import time

class AdminDashboard:
    def __init__(self, server_app):
        self.server = server_app
        self.page = None

    def main(self, page: ft.Page):
        self.page = page
        page.title = "Ghost Server Admin"
        page.theme_mode = ft.ThemeMode.DARK
        
        self.client_list = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("IP")),
                ft.DataColumn(ft.Text("Port")),
                ft.DataColumn(ft.Text("Pseudo")),
                ft.DataColumn(ft.Text("Room")),
                ft.DataColumn(ft.Text("Last Packet")),
                ft.DataColumn(ft.Text("Action")),
            ],
            rows=[]
        )
        
        self.broadcast_input = ft.TextField(label="Broadcast Message", expand=True)
        
        def send_broadcast(e):
            msg = self.broadcast_input.value
            if msg:
                self.server.broadcast_admin_message(msg)
                self.broadcast_input.value = ""
                page.update()

        page.add(
            ft.Text("Server Status", size=30, weight="bold"),
            ft.Row([self.broadcast_input, ft.ElevatedButton("Send", on_click=send_broadcast)]),
            ft.Divider(),
            ft.Text("Connected Clients"),
            self.client_list
        )
        
        # Periodic update loop
        def update_loop():
            while True:
                try:
                    self.refresh_data()
                    time.sleep(1)
                except Exception as e:
                    print(e)
                    break
        
        # Start update thread
        t = threading.Thread(target=update_loop, daemon=True)
        t.start()

    def refresh_data(self):
        if not self.page: return
        
        rows = []
        clients = self.server.get_all_clients()
        
        for c in clients:
            # Story #10: Kick
            kick_btn = ft.ElevatedButton(
                "Kick", 
                on_click=lambda e, client=c: self.kick_client(client),
                bgcolor=ft.Colors.RED, color=ft.Colors.WHITE
            )
            
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(c.addr[0])),
                ft.DataCell(ft.Text(str(c.addr[1]))),
                ft.DataCell(ft.Text(c.pseudo or "Guest")),
                ft.DataCell(ft.Text(c.current_room.name if c.current_room else "-")),
                ft.DataCell(ft.Text(f"{time.time() - c.last_packet:.1f}s ago")),
                ft.DataCell(kick_btn),
            ]))
        
        self.client_list.rows = rows
        self.page.update()

    def kick_client(self, client):
        client.disconnect()


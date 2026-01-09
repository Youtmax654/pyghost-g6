import socket
import flet as ft
import asyncio
import time

class AdminDashboard:
    def __init__(self, server_app):
        self.server = server_app
        self.page = None
        self.client_to_kick = None

    def get_local_ip(self):
        try:
            # Connect to an external server to get the interface IP (doesn't actually send data)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def main_setup(self, page: ft.Page):
        # Separated setup logic to avoid re-adding widgets if main is called multiple times (though likely once)
        self.page = page
        page.title = "Admin Serveur Ghost"
        page.theme_mode = ft.ThemeMode.DARK
        
        local_ip = self.get_local_ip()
        
        self.client_list = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("IP")),
                ft.DataColumn(ft.Text("Port")),
                ft.DataColumn(ft.Text("Pseudo")),
                ft.DataColumn(ft.Text("Salle")),
                ft.DataColumn(ft.Text("Dernier Paquet")),
                ft.DataColumn(ft.Text("Action")),
            ],
            rows=[]
        )
        
        self.broadcast_input = ft.TextField(label="Message Diffusé", expand=True)
        
        # Confirmation Dialog
        self.confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmation"),
            content=ft.Text("Voulez-vous vraiment expulser cet utilisateur ?"),
            actions=[
                ft.TextButton("Oui", on_click=self.confirm_kick),
                ft.TextButton("Non", on_click=self.cancel_kick),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        def send_broadcast(e):
            msg = self.broadcast_input.value
            if msg:
                self.server.broadcast_admin_message(msg)
                self.broadcast_input.value = ""
                page.update()

        page.add(
            ft.Text("Statut Serveur Ghost", size=30, weight="bold"),
            ft.Container(
                content=ft.Column([
                    ft.Text(f"Server IP: {local_ip}", size=20, color=ft.Colors.GREEN),
                    ft.Text(f"Port: 5000", size=20, color=ft.Colors.GREEN),
                    ft.Text("Partagez cette IP avec les clients pour qu'ils se connectent.", size=12, color=ft.Colors.GREY),
                ]),
                padding=10,
                border=ft.border.all(1, ft.Colors.GREEN_900),
                border_radius=5,
                bgcolor=ft.Colors.BLACK54
            ),
            ft.Divider(),
            ft.Row([self.broadcast_input, ft.ElevatedButton("Envoyer", on_click=send_broadcast)]),
            ft.Divider(),
            ft.Text("Clients Connectés"),
            self.client_list
        )
        


    async def main(self, page: ft.Page):
        self.main_setup(page)
        # Async Loop directly awaited
        await self.update_loop()

    async def update_loop(self):
        while True:
            try:
                # Only refresh if dialog is not open to avoid UI conflicts
                if not self.confirm_dialog.open:
                    self.refresh_data()
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Admin Loop Error: {e}")
                await asyncio.sleep(1)

    def refresh_data(self):
        if not self.page: return
        
        rows = []
        clients = self.server.get_all_clients()
        
        for c in clients:
            # Story #10: Kick
            kick_btn = ft.ElevatedButton(
                "Ejecter", 
                on_click=lambda e, client=c: self.prepare_kick(client),
                bgcolor=ft.Colors.RED, color=ft.Colors.WHITE
            )
            
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(c.addr[0])),
                ft.DataCell(ft.Text(str(c.addr[1]))),
                ft.DataCell(ft.Text(c.pseudo or "Invité")),
                ft.DataCell(ft.Text(c.current_room.name if c.current_room else "-")),
                ft.DataCell(ft.Text(f"il y a {time.time() - c.last_packet:.1f}s")),
                ft.DataCell(kick_btn),
            ]))
        
        self.client_list.rows = rows
        self.page.update()

    def prepare_kick(self, client):
        print(f"Preparing to kick {client.pseudo}")
        self.client_to_kick = client
        
        # Ensure we don't duplicate
        if self.confirm_dialog not in self.page.overlay:
            self.page.overlay.append(self.confirm_dialog)
            
        self.confirm_dialog.open = True
        self.page.update()

    def confirm_kick(self, e):
        print("Confirmed Kick")
        if self.client_to_kick:
            print(f"Kicking {self.client_to_kick.pseudo}")
            # Story #10: Message aux autres clients
            pseudo = self.client_to_kick.pseudo or "Un invité"
            self.server.broadcast_admin_message(f"{pseudo} a été expulsé")
            
            self.client_to_kick.disconnect()
            self.client_to_kick = None
            
        self.close_dialog()

    def cancel_kick(self, e):
        print("Cancelled Kick")
        self.client_to_kick = None
        self.close_dialog()

    def close_dialog(self):
        self.confirm_dialog.open = False
        self.page.update()


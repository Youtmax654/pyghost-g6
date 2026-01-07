"""
PyGhost Admin Dashboard
Flet app that runs the server and displays connected clients.
"""
import asyncio
import flet as ft
from server import GhostServer


class AdminDashboard:
    """Admin dashboard for PyGhost server."""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "PyGhost Admin"
        self.page.window.width = 900
        self.page.window.height = 500
        self.page.theme_mode = ft.ThemeMode.DARK
        
        # Create server
        self.server = GhostServer()
        self.server.on_clients_changed = self._on_clients_changed
        
        # Build UI
        self._build_ui()
        
        # Start server in background
        self.page.run_task(self._run_server)
    
    def _build_ui(self):
        """Build the admin UI."""
        # Title
        title = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS, size=32, color=ft.Colors.BLUE_400),
                ft.Text("PyGhost Admin", size=24, weight=ft.FontWeight.BOLD)
            ]),
            padding=ft.Padding.only(bottom=20)
        )
        
        # Status indicator
        self.status_text = ft.Text(
            "🟢 Serveur en écoute sur 127.0.0.1:5555",
            size=14,
            color=ft.Colors.GREEN_400
        )
        
        # Clients table
        self.clients_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("IP:Port", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Pseudo", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Room", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Dernier message", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            border=ft.Border.all(1, ft.Colors.GREY_700),
            border_radius=8,
            heading_row_color=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
            data_row_max_height=50,
        )
        
        # Empty state message
        self.empty_message = ft.Text(
            "Aucun client connecté",
            size=14,
            color=ft.Colors.GREY_500,
            italic=True
        )
        
        # Clients container
        self.clients_container = ft.Container(
            content=ft.Column([
                self.clients_table,
                self.empty_message
            ]),
            expand=True
        )
        
        # Main layout
        self.page.add(
            ft.Container(
                content=ft.Column([
                    title,
                    self.status_text,
                    ft.Divider(height=20),
                    ft.Text("Clients connectés", size=18, weight=ft.FontWeight.W_500),
                    self.clients_container
                ]),
                padding=30,
                expand=True
            )
        )
        
        self._refresh_table()
    
    async def _run_server(self):
        """Run the server in background."""
        try:
            await self.server.start()
        except Exception as e:
            print(f"Server error: {e}")
    
    def _on_clients_changed(self):
        """Called when clients list changes."""
        self.page.run_thread(self._refresh_table)
    
    def _refresh_table(self):
        """Refresh the clients table."""
        rows = []
        
        for session in self.server.all_sessions:
            ip_port = f"{session.addr[0]}:{session.addr[1]}" if session.addr else "-"
            pseudo = session.pseudo or "-"
            room = session.current_room.name if session.current_room else "-"
            last_msg = session.last_message.strftime("%H:%M:%S")
            
            rows.append(ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(ip_port)),
                    ft.DataCell(ft.Text(pseudo)),
                    ft.DataCell(ft.Text(room)),
                    ft.DataCell(ft.Text(last_msg)),
                ]
            ))
        
        self.clients_table.rows = rows
        self.empty_message.visible = len(rows) == 0
        self.clients_table.visible = len(rows) > 0
        self.page.update()


def main(page: ft.Page):
    AdminDashboard(page)


if __name__ == '__main__':
    ft.run(main)

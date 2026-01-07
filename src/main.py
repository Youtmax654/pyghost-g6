"""
PyGhost Flet Desktop Client
"""
import flet as ft
from typing import List
from network import NetworkClient, NotifyType
from controllers.login_controller import LoginController
from controllers.rooms_controller import RoomsController
from protocol import RoomInfo


class GhostApp:
    """Main Ghost application."""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Ghost"
        self.page.window.width = 800
        self.page.window.height = 600
        
        self.pseudo: str = ""
        self.current_room: RoomInfo | None = None
        self.network = NetworkClient()
        
        # Setup controllers
        self.login_controller = LoginController(
            page=self.page,
            network=self.network,
            on_login_success=self._on_login_success
        )
        
        self.rooms_controller = RoomsController(
            page=self.page,
            network=self.network,
            on_room_joined=self._on_room_joined
        )
        
        # Setup remaining network callbacks
        self.network.on_notify = self._on_notify
        self.network.on_disconnected = self._on_disconnected
        
        # Build UI
        self._build_ui()
        
        # Start network and show login
        self.network.start()
        self.login_controller.show()
    
    def _build_ui(self):
        """Build the main UI."""
        # Game view (placeholder for now)
        self.game_view = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Dans la room",
                    size=24,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Container(height=10),
                ft.Text(
                    "",
                    size=16,
                    key="room_name"
                ),
                ft.Text(
                    "",
                    size=14,
                    color=ft.Colors.GREY_500,
                    key="players_list"
                )
            ]),
            visible=False,
            padding=20
        )
        
        self.page.add(self.rooms_controller.view)
        self.page.add(self.game_view)
    
    def _on_login_success(self, pseudo: str):
        """Called when login succeeds."""
        self.pseudo = pseudo
        self.rooms_controller.show()
    
    def _on_room_joined(self, room: RoomInfo, players: List[str]):
        """Called when room is joined."""
        self.current_room = room
        self.game_view.visible = True
        
        # Update game view content
        for control in self.game_view.content.controls:
            if hasattr(control, 'key'):
                if control.key == "room_name":
                    control.value = f"Room: {room.name}"
                elif control.key == "players_list":
                    control.value = f"Joueurs: {', '.join(players)}"
        
        self.page.update()
    
    def _on_notify(self, notify_type: NotifyType, pseudo: str):
        """Called when a player joins/leaves the room."""
        def update_ui():
            if notify_type == NotifyType.JOIN:
                print(f"{pseudo} a rejoint la room")
            else:
                print(f"{pseudo} a quitté la room")
        
        self.page.run_thread(update_ui)
    
    def _on_disconnected(self):
        """Called when disconnected from server."""
        self.game_view.visible = False
        self.rooms_controller.hide()
        self.login_controller.on_disconnected()


def main(page: ft.Page):
    GhostApp(page)


if __name__ == '__main__':
    ft.run(main)

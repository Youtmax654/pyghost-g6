"""
Rooms controller - handles room selection flow.
"""
from typing import Callable, List, Optional
import flet as ft
from network import NetworkClient, NotifyType
from protocol import RoomInfo


class RoomsController:
    """Controller for room selection."""
    
    def __init__(
        self,
        page: ft.Page,
        network: NetworkClient,
        on_room_joined: Callable[[RoomInfo, List[str]], None]
    ):
        self.page = page
        self.network = network
        self.on_room_joined = on_room_joined
        self.rooms: List[RoomInfo] = []
        self.current_room: Optional[RoomInfo] = None
        
        # Register network callbacks
        self.network.on_room_list = self._on_room_list
        self.network.on_room_joined = self._on_joined
        
        # Build UI
        self._build_view()
    
    def _build_view(self):
        """Build the room selection view."""
        self.rooms_list = ft.Column(spacing=10)
        
        self.loading = ft.ProgressRing(
            visible=True,
            width=30,
            height=30,
        )
        
        self.view = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Sélectionnez une Room",
                        size=28,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Divider(),
                    ft.Text(
                        "Rejoignez une table pour commencer à jouer.",
                        size=14,
                        color=ft.Colors.GREY_400,
                    ),
                    ft.Container(height=20),
                    self.loading,
                    self.rooms_list,
                ],
                expand=True,
            ),
            expand=True,
            visible=False,
            padding=20,
        )
    
    def show(self):
        """Show the room selection view."""
        self.view.visible = True
        self.loading.visible = True
        self.rooms_list.controls.clear()
        self.page.update()
    
    def hide(self):
        """Hide the room selection view."""
        self.view.visible = False
        self.page.update()
    
    def _on_room_list(self, rooms: List[RoomInfo]):
        """Callback: room list received from server."""
        def update_ui():
            self.rooms = rooms
            self.loading.visible = False
            self.rooms_list.controls.clear()
            
            for room in rooms:
                self.rooms_list.controls.append(self._create_room_card(room))
            
            self.page.update()
        
        self.page.run_thread(update_ui)
    
    def _create_room_card(self, room: RoomInfo) -> ft.Card:
        """Create a card for displaying a room."""
        is_full = room.players >= room.max_players
        
        return ft.Card(
            content=ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.TABLE_RESTAURANT,
                            size=40,
                            color=ft.Colors.BLUE_400,
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    room.name,
                                    size=18,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Text(
                                    f"Joueurs: {room.players}/{room.max_players}",
                                    size=12,
                                    color=ft.Colors.GREY_400,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.FilledButton(
                            "Rejoindre",
                            icon=ft.Icons.LOGIN,
                            disabled=is_full,
                            on_click=lambda e, r=room: self._join_room(r),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=15,
            ),
        )
    
    def _join_room(self, room: RoomInfo):
        """Request to join a room."""
        self.current_room = room
        self.network.join_room(room.room_id)
    
    def _on_joined(self, players: List[str]):
        """Callback: room joined successfully."""
        def update_ui():
            if self.current_room:
                self.hide()
                self.on_room_joined(self.current_room, players)
        
        self.page.run_thread(update_ui)
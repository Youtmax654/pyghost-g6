import flet as ft
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client.views.game_view import GameClientApp

def main(page: ft.Page):
    app = GameClientApp(page)

if __name__ == "__main__":
    ft.run(main)

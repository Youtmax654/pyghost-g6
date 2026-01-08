# Ghost Game - Python Client/Server

## Installation

1. Install Python 3.10+
2. Install Flet:
   ```bash
   uv add "flet[all]"
   ```

## Usage

### Server
Run the server first. It will start the TCP server on port 5000 and the Admin Dashboard.
```bash
python3 server/main.py
```

### Client
Run the client (you can run multiple instances).
```bash
python3 client/main.py
```

## Features Implemented
- **Protocol**: Custom binary protocol (Big-Endian) with OpCodes.
- **Login/Rooms**: Unique pseudo check, Room listing and joining.
- **Game Logic**: Ghost game rules (Fragments, Dictionary check, Challenge).
- **Admin**: Flet Dashboard with Kick and Broadcast.
- **Bonuses**:
  - Heartbeat (PING/PONG) with timeout.
  - Load Balancer limit (5 clients).
  - Room List feature.

## Architecture
- `/common`: Shared protocol and utils.
- `/server`: Threaded TCP Server, MVC structure (ClientHandler, RoomManager, GameState).
- `/client`: Flet UI, NetworkManager.

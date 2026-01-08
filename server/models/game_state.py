class GameState:
    def __init__(self):
        self.frag = ""
        self.players = [] # List of pseudos
        self.scores = {} # pseudo -> letters (e.g. "G", "GH")
        self.current_player_idx = 0
        self.dictionary = self.load_dictionary()

    def load_dictionary(self):
        # Pour l'exercice, on utilise un petit dictionnaire en dur.
        # Dans un vrai projet, on chargerait un fichier.
        return {
            "BONJOUR", "MONDE", "PYTHON", "RESEAU", "SOCKET", "GHOST", "TEST",
            "MANGER", "TABLE", "CHAISE", "MAISON", "APPLE", "BANANA", "ORANGE"
        }

    def add_player(self, pseudo):
        if pseudo not in self.players:
            self.players.append(pseudo)
            self.scores[pseudo] = ""
   
    def remove_player(self, pseudo):
        if pseudo in self.players:
            # Need to handle turn if current player leaves
            idx = self.players.index(pseudo)
            if idx < self.current_player_idx:
                self.current_player_idx -= 1
            self.players.remove(pseudo)
            del self.scores[pseudo]
            if self.current_player_idx >= len(self.players):
                self.current_player_idx = 0

    def get_current_player(self):
        if not self.players:
            return None
        return self.players[self.current_player_idx]

    def next_turn(self):
        if not self.players:
            return
        self.current_player_idx = (self.current_player_idx + 1) % len(self.players)

    def play_letter(self, letter):
        self.frag += letter.upper()
        # Verify if strict word (loss condition logic handled by Controller usually,
        # but Model can return status).
        # Rule 2: If completes a valid word > 3 letters, they lose.
        if len(self.frag) > 3 and self.frag in self.dictionary:
            return "LOSE_WORD"
        return "CONTINUE"

    def challenge(self):
        # Rule 3: Challenge previous player.
        # If no word can start with current frag, previous player loses.
        # Else, challenger loses.
        # We need to check if ANY word starts with self.frag
        # BUT the rule says "Un joueur peut Challenger le précédent s'il pense qu'aucun mot ne peut commencer..."
        # So check: exists w in dict such that w.startswith(frag).
        
        valid_exists = any(w.startswith(self.frag) for w in self.dictionary)
        if not valid_exists:
            # The fragment is invalid -> Previous player (who wrote the last letter) was bluffing or stuck -> Previous player loses.
            return "PREVIOUS_LOSES"
        else:
            # Fragment is valid (exists a word) -> Challenger was wrong -> Challenger loses.
            return "CHALLENGER_LOSES"

    def punish_player(self, pseudo):
        # Add a letter G-H-O-S-T
        if pseudo not in self.scores:
            return
        
        current = self.scores[pseudo]
        ghost = "GHOST"
        if len(current) < 5:
            self.scores[pseudo] += ghost[len(current)]
        
        # Reset fragment
        self.frag = ""
        
        if len(self.scores[pseudo]) >= 5:
            return "ELIMINATED"
        return "PUNISHED"

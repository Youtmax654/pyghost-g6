# PROTOCOL.md

Transport : **TCP uniquement**

## Frontières Protocol / Application

### Le protocole :

- gère **la connexion**
- gère **les sessions**
- gère **les rooms**
- transporte des messages
- orchestre certaines séquences (login -> join -> data)

### L'application : 

- définit ses propres types de messages
- interprète les données contenues dans `DATA`
- décide des règles métier (jeu, chat, etc.)

**Le protocole ne connaît pas le jeu PyGhost**

## Format des messages

Tous les messages suivent ce format :

`[ Taille ] [ Payload ]`

- Taille : UInt32 Big-Endian
- Payload = [OpCode (1o)] + [Données]

## Exemples de messages

### 1. Connexion

- Direction : **Client -> Serveur**

- Format : `[1o TaillePseudo] [Pseudo UTF-8]`

- Exemple : `05 41 6C 69 63 65   // "Alice"`

### 2. Réponse de la connexion

- Format : `[1o Status]`

  - 0x00 = OK

  - 0x01 = REFUSED

- Exemple : `00`
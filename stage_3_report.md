# `counterTrak` Development Plan
## Relational Schema
### Overview
The `counterTrak` relational schema is meant to capture detailed *Counter-Strike 2* game meta-data obtained through Valve's Game State Integration (GSI) system. The schema is to facilitate tracking and analysis of player performance metrics across matches, round-by-round states, equipped weapons, and match outcomes. The schema is constructed to support both historical analysis and real-time performance tracking.
### Textual Implementation
Below is the textual implementation of the `counterTrak` relational schema, which was rendered using the *MathJax* typesetting display engine. Please do note that the Weapons relation will be pre-populated, as it acts as a reference-table for all known weapons currently available in CS2:
```math
 \begin{aligned} 
 &\text{Users}( \underline{steam\_id}, \text{email, password\_hash} ) \\ \\
 &\text{SteamAccounts}(\underline{steam\_id}, \text{user\_id, auth\_token, player\_name} ) \\
 &\exists \quad \text{FK: SteamAccount.user\_id references User}(\underline{user\_id})\\ \\
 &\text{Matches}( \underline{match\_id},\text{mode, map\_name, start\_timestamp, end\_timestamp,}\\ & \qquad \quad \; \text{rounds\_played, team\_ct\_score, team\_t\_score} ) \\ \\
 &\text{Rounds}( \underline{match\_id, round\_number}, \text{phase, timestamp, winning\_team,} \\ & \qquad \quad \; \text{win\_condition}) \\
 &\exists \quad \text{FK: Round.match\_id references Match}(\underline{match\_id}) \\ \\
 &\text{PlayerRoundStates}( \underline{match\_id, round\_number, steam\_id} \text{, health, armor,} \\
 & \qquad \qquad \qquad \qquad \quad \text{money, equip\_value, round\_kills}) \\
 &\exists \quad \text{FK: PlayerRoundStates.(match\_id, round\_number) ref. Round}(\underline{match\_id, round\_number}) \\
 &\exists \quad \text{FK: PlayerRoundStates.steam\_id references SteamAccount}(\underline{steam\_id}) \\ \\
 &\text{Weapons}(\underline{weapon\_id}\text{, name, type, max\_clip}) \\ \\
 &\text{PlayerWeapons}(\underline{match\_id, round\_number, steam\_id, weapon\_id}\text{, state, ammo\_clip,} \\ 
 & \qquad \qquad \qquad \quad \text{ammo\_reserve, paintkit}) \\
 &\exists \quad \text{FK: PlayerWeapons.(match\_id, round\_number, steam\_id) references} \\
 & \qquad \quad \; \; \text{PlayerRoundStates}(\underline{match\_id, round\_number, steam\_id}) \\
 &\exists \quad \text{FK: PlayerWeapons.weapon\_id references Weapons}(\underline{weapon\_id}) \\ \\
 
 &\text{PlayerMatchStats}(\underline{steam\_id, match\_id}\text{, kills, deaths, assists, mvps, score}) \\
 &\exists \quad \text{FK: PlayerMatchStats.steam\_id references SteamAccount}(\underline{steam\_id}) \\
 &\exists \quad \text{FK: PlayerMatchStats.match\_id references Match}(\underline{match\_id}) 
 \end{aligned}
```
### Functional Dependencies
 Below are all of the functional dependencies present in the `counterTrak` relational schema, in the form of a bulleted list. The schema in question has been carefully constructed to adhere to the specifications of *Boyce-Codd Normal Form*:

**User relation**:
- user_id → email, password_hash
**SteamAccount relation:**
- steam_id → user_id, auth_token, player_name
**Match relation:**
- match_id → mode, map_name, start_timestamp, end_timestamp, rounds_played, team_ct_score, team_t_score
**Round relation:**
- (match_id, round_number) → phase, timestamp, winning_team, win_condition
**PlayerRoundState relation:**
- (match_id, round_number, steam_id) → health, armor, money, equip_value, round_kills
**Weapon relation:**
- weapon_id → name, type, max_clip
- name → weapon_id (name is also a candidate key)
**PlayerWeapon relation:**
- (match_id, round_number, steam_id, weapon_id) → state, ammo_clip, ammo_reserve, paintkit
**PlayerMatchStat relation:**
- (steam_id, match_id) → kills, deaths, assists, mvps, score
### SQL Implementation
---
In addition to the textual representation of the `counterTrak` relational schema, we have also provided the SQL implementation in accordance to the attributes, entities, and relations seen in the ER diagram. The SQL syntax seen below is compatible with PostgreSQL, which is our preferred RDBMS provider:
```sql
-- Users table (for counterTrak users, not CS2 users)
CREATE TABLE Users(
	user_id SERIAL PRIMARY KEY,
	email VARCHAR(255) NOT NULL,
	password_hash VARCHAR(255) NOT NULL
);

-- Steam accounts linked to Users
-- steam_id validation can be performed by
-- making an HTTPS GET request to the URL:
-- https://steamcommunity.com/id/<steam_id>
CREATE TABLE SteamAccounts(
	steam_id VARCHAR(64) PRIMARY KEY,
	user_id INTEGER REFERENCES Users(user_id),
	auth_token VARCHAR(128),
	player_name VARCHAR(100) NOT NULL
);

-- Match information
CREATE TABLE Matches(
	match_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	game_mode VARCHAR(32) NOT NULL,
	map_name VARCHAR(64) NOT NULL,
	start_timestamp TIMESTAMP NOT NULL,
	end_timestamp TIMESTAMP NOT NULL,
	rounds_played INTEGER DEFAULT 0,
	team_ct_score INTEGER DEFAULT 0,
	team_t_score INTEGER DEFAULT 0
);

-- Round information (part of Match)
CREATE TABLE Rounds(
	match_id UUID REFERENCES Matches(match_id) ON DELETE CASCADE,
	round_number INTEGER NOT NULL,
	phase VARCHAR(32) NOT NULL,
	round_timestamp TIMESTAMP NOT NULL,
	winning_team VARCHAR(32),
	win_condition VARCHAR(64),
	PRIMARY KEY (match_id, round_number)
);

-- Player state during each round
CREATE TABLE PlayerRoundStates(
	match_id UUID NOT NULL,
	round_number INTEGER NOT NULL,
	steam_id VARCHAR(64) NOT NULL REFERENCES SteamAccounts(steam_id),
	health INTEGER NOT NULL,
	armor INTEGER NOT NULL,
	player_money INTEGER NOT NULL,
	equip_value INTEGER NOT NULL,
	round_kills INTEGER NOT NULL DEFAULT 0,
	PRIMARY KEY (match_id, round_number, steam_id),
	FOREIGN KEY (match_id, round_number) REFERENCES Rounds(match_id, round_number)
);

-- Weapons available in the game
CREATE TABLE Weapons(
	weapon_id INTEGER PRIMARY KEY,
	weapon_name VARCHAR(64) UNIQUE NOT NULL,
	weapon_type VARCHAR(32) NOT NULL,
	max_clip INTEGER
);

-- Pre-populate with known weapons
INSERT INTO Weapons (weapon_id, weapon_name, weapon_type, max_clip) VALUES
(1, 'weapon_knife', 'Knife', NULL),
(2, 'weapon_knife_t', 'Knife', NULL),
(3, 'weapon_glock', 'Pistol', 20),
(4, 'weapon_hkp2000', 'Pistol', 13),
(5, 'weapon_usp_silencer', 'Pistol', 12),
(6, 'weapon_p250', 'Pistol', 13),
(7 'weapon_fiveseven', 'Pistol', 20),
(8, 'weapon_deagle', 'Pistol', 7), 
(9, 'weapon_elite', 'Pistol', 30), 
(10, 'weapon_tec9', 'Pistol', 18), 
(11, 'weapon_revolver', 'Pistol', 8), 
(12, 'weapon_mac10', 'Submachine Gun', 30), 
-- ... and so on for all weapons
);

-- Weapons equipped by players in each round
CREATE TABLE PlayerWeapons(
    match_id UUID NOT NULL,
    round_number INTEGER NOT NULL,
    steam_id VARCHAR(64) NOT NULL,
    weapon_id INTEGER NOT NULL REFERENCES Weapons(weapon_id),
    weapon_state VARCHAR(32) NOT NULL,
    ammo_clip INTEGER,
    ammo_reserve INTEGER,
    paintkit VARCHAR(64) DEFAULT 'default',
    PRIMARY KEY (match_id, round_number, steam_id, weapon_id),
    FOREIGN KEY (match_id, round_number, steam_id) REFERENCES PlayerRoundStates(match_id, round_number, steam_id)
);

-- Player statistics for each match
CREATE TABLE PlayerMatchStats(
    steam_id VARCHAR(64) REFERENCES SteamAccounts(steam_id),
    match_id UUID REFERENCES Matches(match_id),
    kills INTEGER NOT NULL DEFAULT 0,
    deaths INTEGER NOT NULL DEFAULT 0,
    assists INTEGER NOT NULL DEFAULT 0,
    mvps INTEGER NOT NULL DEFAULT 0,
    score INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (steam_id, match_id)
);

-- Performance-optimizing indexes
CREATE INDEX idx_rounds_match ON rounds(match_id);
CREATE INDEX idx_player_states_match_round ON player_round_states(match_id, round_number);
CREATE INDEX idx_player_weapons_state ON player_weapons(match_id, round_number, steam_id);
CREATE INDEX idx_player_stats_match ON player_match_stats(match_id);
```
## Technology Stack
### RDBMS Provider
### Backend System
### Frontend System
## Data Collection

### Methods
Data Collection will be facilitated through CS2's Game State Integration (GSI) system as documented by Valve. The process involves:
1. Creating a GSI configuration file (`gamestate_integration_countertrak.cfg`) in the CS2 game directory that specifies:
	- The HTTP endpoint on our server (e.g., `http://localhost:3000` for development)
	- Authentication token for payload verification
	- Data components to collect (player_state, player_weapons, round, map, etc.)
2. Setting up an HTTP server using Python that:
	- Receives JSON payloads from CS2
	- Authenticates the requests using the configured token
	- Processes the payload using our PayloadExtractor class
	- Stores extracted data in PostgreSQL through Django's ORM
3. Implementing delta-based updates to minimize database writes:
	- Track changes between states
	- Only update database records when meaningful changes occur
	- Use transactions to ensure data consistency
The implementation will leverage the existing code from our proof-of-concept originally shared in the Stage 2 Report, with several changes. We'll also have to configure our system to support multi-threading, in order to handle many concurrent game clients forwarding HTTP POST requests to the server. This may involve rewriting significant amounts of said proof-of-concept to intermesh with the Django backend system we are to implement.
## Logistics
### Labor Division
### Milestone-Based Timeline

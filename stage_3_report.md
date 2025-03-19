# `counterTrak` Development Plan
## Relational Schema
### Overview
The `counterTrak` relational schema is meant to capture detailed *Counter-Strike 2* game meta-data obtained through Valve's Game State Integration (GSI) system. The schema is to facilitate tracking and analysis of player performance metrics across matches, round-by-round states, equipped weapons, and match outcomes. The schema is constructed to support both historical analysis and real-time performance tracking.
### Textual Implementation
Below is the textual implementation of the `counterTrak` relational schema, which was rendered using the *MathJax* typesetting display engine:
 $$ 
 \begin{aligned} 
 &\text{User}( \underline{steam\_id}, \text{email, password\_hash} ) \\
 &\text{SteamAccount}(\underline{steam\_id}, \text{user\_id, auth\_token, player\_name} ) \\
 &\exists \quad \text{FK: SteamAccount.user\_id references User}(\underline{user\_id})\\
 &\text{Match}( \underline{match\_id},\text{mode, map\_name, start\_timestamp, end\_timestamp,}\\ & \qquad \quad \; \text{rounds\_played, team\_ct\_score, team\_t\_score} ) \\
 &\text{Round}( \underline{match\_id, round\_number}, \text{phase, timestamp, winning\_team,} \\ & \qquad \quad \; \text{win\_condition}) \\
 &\exists \quad \text{FK: match\_id references Match}(\underline{match\_id}) \\
 &\text{PlayerRoundStates}( \underline{match\_id, round\_number, steam\_id} \text{, health, armor,} \\
 & \qquad \qquad \qquad \qquad \quad \text{money, equip\_value, round\_kills}) \\
 
 \end{aligned}
 $$
### Functional Dependencies
### SQL Implementation

## Technology Stack
### RDBMS Provider
### Backend System
### Frontend System
## Data Collection
### Methods
## Logistics
### Labor Division
### Milestone-Based Timeline
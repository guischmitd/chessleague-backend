# DB Schema

## Events table
**Contains**: All ACL events including quarterly major tournaments and cups
- id
- number of round stage rounds
- round stage rounds deadlines
- playoffs method (**MVP** > grand final between top 2. tie break as necessary)
- tiebreak method (**MVP** > 1 x 5+3 blitz random sides)
- status (active, current phase, current round)
- players

## Members table
- id
- ACL username
- lichess username
- events subscribed (IDs of events table ACL I, ACL II, Cups)
- ACL elo
- ACL Medals
- ACL Achievements

## Games table
**Contains**: All games uploaded by members that passed validation and confirmation.
- id
- date added
- date played
- raw response (json)
- added by (member ID)
- event ID
- event phase
- time format
- result (white, black, draw)
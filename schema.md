# DB Schema

## Events table
**Contains**: All ACL events including quarterly major tournaments and cups
- [x] id
- [x] start timestamp
- [x] number of round stage rounds
- [x] round stage deadline
- [x] playoffs method (**MVP** > grand final between top 2. tie break as necessary)
- [x] tiebreak method (**MVP** > 1 x 5+3 blitz random sides)
- [x] active
- [x] current phase
- [ ] current round

## Members table
- [x] id
- [x] ACL username
- [x] lichess username
- [ ] lichess elo
- [ ] events subscribed (IDs of events table ACL I, ACL II, Cups)
- [x] ACL elo
- [ ] ACL Medals
- [ ] ACL Achievements
- [x] date joined

## Games table
**Contains**: All games uploaded by members that passed validation and confirmation.
- [x] id
- [x] date added
- [x] date played
- [x] lichess game data (json)
- [ ] added by (member ID)
- [x] event ID
- [ ] event phase
- [x] time format (time_base + time_increment)
- [x] white
- [x] black
- [x] outcome (white, black, draw)
- [x] winner (player name or null in case of draw)

## Fixtures
- [ ] id
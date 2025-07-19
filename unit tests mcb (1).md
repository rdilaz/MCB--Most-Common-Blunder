# Game Unit Tests

# Notes

## Regarding the $\# symbols:

These are Numeric Annotation Glyphs (NAGs) that evaluate moves:  
$1 \= Great move (\!)  
**$2 \= Mistake (?)**  
$3 \= Excellent move (\!\!)  
**$4 \= Blunder (??)**  
$5 \= Interesting move (\!?)  
**$6 \= Inaccuracy (?\!)**  
**$9 \= Missed Opportunity (x)**  
Moves followed with $4 should always be picked up by MCB analysis (although PGNS scraped from [chess.com](http://chess.com) api will not have these, just using them for now). Ideally, except in cases where the move is not generalizable, $9 and $6 and $2 should also be picked up, especially if the move resulted in large percentage drop

## Regarding “You” and “They”

A majority of the comments in the pgns {} are from [chess.com](http://chess.com). If the comment mentions “You” it will always be referring to whatever color “roygbiv6” is playing.  
“They” will always be referring to whatever player/color is not roygbiv6.

# Game 1: Ganesan1632 vs roygbiv6 (black)

## PGN W/ [Chess.com](http://Chess.com) Comments:

\[Date "2025.07.19"\]  
\[White "Ganesan16362"\]  
\[Black "roygbiv6"\]  
\[Result "1-0"\]  
\[Timezone "UTC"\]  
\[ECO "D02"\]  
\[ECOUrl "https://www.chess.com/openings/Queens-Pawn-Opening-Zukertort-Variation"\]  
\[UTCDate "2025.07.19"\]  
\[UTCTime "02:03:30"\]  
\[WhiteElo "630"\]  
\[BlackElo "597"\]  
\[TimeControl "600"\]  
\[Termination "Ganesan16362 won by checkmate"\]  
\[StartTime "02:03:30"\]  
\[EndDate "2025.07.19"\]  
\[EndTime "02:12:22"\]  
\[Link "https://www.chess.com/analysis/game/live/140854881174/analysis?move=13"\]

1\. Nf3 d5  
2\. d4 Nf6  
3\. Be3 Bf5  
4\. Nc3 Nc6  
5\. h3 e6  
6\. g4 Be4  
7\. Ne5 **$4** {white hung the white squared rook on h1, which can be taken by blacks white squared bishop on e4} Nxe5 **$9** {Black missed the opportunity to win the rook}  
8\. f3 **$9** {white missed opportunity to make winning capture Nxe4} Nxf3+ **$4** {Black gives up knight on f3, since its being attacked by a piece of lesser value, the pawn on e2}  
9\. exf3 Bg6  
10\. Bg5 **$6** {White missed a chance to develop a queen off its starting square.} Bb4  
11\. Qe2 Bxc3+  
12\. bxc3 O-O **$6** {Blacks move doesn't hurt but also doesn't help}  
13\. O-O-O **$6** {Not the worst move, but definitely not the best.} c6 **$6** {Black missed an opportunity to kick a bishop.}  
14\. c4 **$2** {They missed a chance to push the pawns further toward the king.} Re8 **$6** {Black loses advantage}  
15\. cxd5 **$2** {White allowed black to play Qa5 to pin pawn on d5 to hung bishop on g5} exd5 **$6** {Missed opportunity to pin}  
16\. Qd2 h6  
17\. Bh4 Qd6  
18\. g5 **$6** {lost pawn} Nd7 **$9** {You missed an opportunity to tactically win a pawn.}  
19\. gxh6 gxh6  
20\. Bd3 **$6 {**Doesnt Help**}** Bxd3  
21\. Qxd3 **$2** {Didn't recapture with the right piece cxd3 was better} Qf4+ $1  
22\. Kb1 Qxh4  
23\. Rhg1+ Kf8  
24\. Qa3+ Re7  
25\. Rde1 Qxd4 **$4** {You permitted the opponent to checkmate the king.}  
26\. Qxe7\# $1 1-0

# Game 2: Dinnrztily vs roygbiv6(white)

\[White "roygbiv6"\]  
\[Black "Dinnrztily"\]  
\[Result "0-1"\]  
\[TimeControl "600"\]  
\[Termination "Dinnrztily won by checkmate"\]  
\[StartTime "04:03:13"\]  
\[EndDate "2025.07.18"\]  
\[EndTime "04:19:06"\]

1\. d4 d5 2\. Bf4 Nc6 3\. e3 e5 $6  
4\. Nf3 **$4 {That move leaves your bishop undefended and free to take. You overlooked an opportunity to capture a free pawn.}** f6 **$9 {They overlooked an opportunity to capture a vulnerable bishop.}**  
5\. dxe5 fxe5  
6\. Nxe5 d4 $2 {They missed a chance to recapture a piece.}  
7\. Nxc6 $1 bxc6  
8\. Bd3 **$6 {You overlooked an opportunity to win material through a tactic.}** Bc5 **$2 {Allowed Qd5 fork )**  
9\. Qh5+ $1 g6 10\. Qxc5 dxe3 11\. Qxc6+ Bd7 12\. Qe4+ Ne7 13\. Qxe3  
c6 14\. Bc4 Qa5+  
15\. c3 **$6 {You missed a better way to block a check from the opposing queen. You allowed the opponent to take an open file with a rook.}** O-O-O  
16\. Qxe7 **$6 {You permitted the opponent to win a queen by pinning a piece to the king.}** Rhe8  
17\. Qxe8 Rxe8+  
18\. Be3 $1 Qc5  
19.Nd2 Rxe3+ 20\. fxe3 Qxe3+ 21\. Be2 Bg4  
22\. O-O-O **$4 {Your bishop is undefended, so this move loses material.}** Qxe2 **$6 {They missed a better way to capture a free bishop.}**  
 23\. Rde1 Qxg2  
24\. h3 **$6 {You permitted the opponent to eventually win a pawn.}** Be2 25\. h4 a5 26\. Rhg1 Qf2 27\. Ne4 Qe3+  
28\. Nd2 a4 **$4 {You are now able to win a bishop by adding pressure to a pinned piece.}**  
 29\. a3 **$9 {You overlooked an opportunity to win a bishop by adding pressure to a pinned piece.}** c5 **$4 {You get a chance to win a bishop by adding pressure to a pinned piece.}**  
30\. b4 **$4 {You allowed the opponent to eventually win a knight. You missed an opportunity to win a bishop by adding pressure to a pinned piece.}** axb3 **$9 {They had a better way to tactically win a knight.}**  
 31\. a4 **$2** {You allowed the opponent to force eventual checkmate.} Qxc3+ $1  
32\. Kb1 Qc2+  
33\. Ka1 b2+ **$9 {They missed a chance to checkmate the king.}**  
34\. Ka2 Qxd2 **$9** {**They missed the forced checkmate, giving you an opportunity to stay in the game.}**  
35\. Rb1 **$2** **{You permitted the opponent to force eventual checkmate.**}Bc4+ $1  
36\. Ka3 Qb4\# 0-1

Ganesan16362 vs roygbiv6
📅 2025-07-19 11:12 • 🎯 Rapid • 🏆 Rated
4 blunders
🔗 View

Hide blunders
▲
4 blunders found in chronological order:
🎯 Move 7: Missed Material Gain-27.5% ↓
Your move Nxe5 missed a chance to win a Rook with Bxh1.
🎯 Move 8: Allowed Winning Exchange for Opponent-23.3% ↓
Your move Nxf3+ left your Knight on f3 defended, but the resulting exchange sequence starting with exf3 wins material for your opponent.
🎯 Move 18: Allowed Winning Exchange for Opponent-16.8% ↓
Your move Nd7 left your Pawn on h6 defended, but the resulting exchange sequence starting with gxh6 wins material for your opponent.
🎯 Move 25: Allowed Checkmate-83.0% ↓
Your move Qxd4 allows the opponent to force checkmate in 1.
roygbiv6 vs Dinnrztily
📅 2025-07-18 13:19 • 🎯 Rapid • 🏆 Rated
7 blunders
🔗 View

Hide blunders
▲
7 blunders found in chronological order:
🎯 Move 4: Missed Material Gain-51.2% ↓
Your move Nf3 missed a chance to win a Pawn with dxe5.
🎯 Move 16: Missed Fork-15.1% ↓
Your move Qxe7 missed a fork with Qe5. The Queen could have attacked the Queen and Knight and Rook.
🎯 Move 22: Hanging a Piece-29.4% ↓
Your move O-O-O left your Bishop on e2 completely undefended.
🎯 Move 24: Mistake-12.0% ↓
Your move h3 dropped your win probability by 12.0%. The best move was Rhg1.
🎯 Move 29: Allowed Fork-42.1% ↓
Your move a3 allows the opponent to play Qf2, creating a fork with their Queen that attacks your Rook and Rook.
🎯 Move 30: Allowed Checkmate-86.6% ↓
Your move b4 allows the opponent to force checkmate in 6.
🎯 Move 31: Allowed Checkmate-11.4% ↓

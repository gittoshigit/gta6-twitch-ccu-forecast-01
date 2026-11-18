[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/gittoshigit/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/gittoshigit/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

# GTA VI launch-day Twitch viewer forecaster

Entry for make.fun bounty **gta6-twitch-ccu-forecast-01**.

`main.py` (Python 3.13, standard library only) reads a case — the first hour's
Twitch viewer count for the Grand Theft Auto VI category plus past big launches'
release-day curves bundled in the case — and writes five quantiles
(5/25/50/75/95%) for each of hours 2–24 of release day.

Method: for every comparable launch in the case, take the log ratio of each
hour's viewers to that launch's hour-1 viewers; pool the ratios per hour with
weights that favour launches of similar hour-1 scale; report the weighted
empirical quantiles, lightly smoothed across hours. If a case carries too
little comparable data, it falls back to the persistence baseline.
Deterministic; runs in well under a second per case.

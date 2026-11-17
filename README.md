# GTA VI Twitch CCU forecast — entry

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/ArchvrTech/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/ArchvrTech/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts Twitch viewers for hours 2–24 of a launch day from the case's
hour-1 print, using the launch-day curves of the case's comparables.

## Approach

Launch-day audience curves differ wildly in absolute terms, but their
shape — the log-ratio of each hour's viewers to hour 1's — is strongly
predicted by how big hour 1 already is. A tiny hour 1 means the audience
is still building (day peaks 100x–1000x higher); a huge hour 1 means the
launch is already at full strength (day peaks only ~1x–2.7x higher).

For each hour h = 2..24 the program takes a weighted neighbourhood of the
comparables whose hour-1 size is closest (in log space) to this case's
(12 nearest, Gaussian kernel bandwidth 1.0), and reads the median shape
(weighted mean of ln(viewers_h / viewers_1)) and spread (weighted sd) off
them. Quantiles are q_tau = p1 * exp(m_h + z_tau * s_h) with Student-t(8)
z-values (-1.860, -0.706, 0, 0.706, 1.860) for heavier tails.

## Validation (leave-one-out over the kit's 37 comparable launches)

Mean pinball loss, this entry vs the house baseline:

| set | this entry | baseline |
|---|---|---|
| all 37 launches | **0.398** | 0.930 |
| big launches (hour-1 ≥ 20k) | **0.261** | 0.321 |
| very big (hour-1 ≥ 100k) | **0.217** | 0.261 |

90% coverage 0.89–0.92 (honest target 0.90). Runtime ~0.05 s per case
(limit 8 s); outputs deterministic (byte-identical across runs).

## Run it

```sh
python3 main.py
```

Reads `$MAKEFUN_INPUT_DIR` (default `/input`), writes `$MAKEFUN_OUTPUT_DIR` (default `/output`), one `.out` per `.in`.

## Files

- `main.py` — the entry (Python 3.13, standard library only).
- `LICENSE` — MIT (from `makefun init`).

---

<sub>Entered on [make.fun](https://make.fun/?ref=tbrxb1pa&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>

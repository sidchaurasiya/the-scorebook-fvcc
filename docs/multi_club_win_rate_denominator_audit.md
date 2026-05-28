# Multi-club win rate denominator audit

This audit compares total Hall of Fame `Matches` against the `matches_with_result` denominator used by deploy-safe `player_win_rates.csv`.

Why differences happen:
- `Matches` counts total recorded club appearances from aggregate processed batting/bowling/fielding tables.
- `Win %` counts only appearances in matches with a classified result from local match-centre summaries.
- Pending, abandoned, cancelled, no-result, or otherwise unattributable outcomes lower the win-rate denominator without changing total appearances.

UI decision:
- Keep `Matches` in Detailed Records as total career appearances.
- Keep `Win %` sourced from result-classified matches only.
- Best Win % cards should label the denominator explicitly as `matches with results`.

## Summary by club

| Club | Players compared | Players with denominator mismatch | Old best-win qualifier | New best-win qualifier |
| --- | ---: | ---: | --- | --- |
| Fiji Victorian Cricket Club | 288 | 151 | Jimmy Sharma (65.9% · 86 total / 82 result) | Jimmy Sharma (65.9% · 82 result) |
| Southside East Caulfield Cricket Club | 415 | 194 | Sajan Patel (61.4% · 63 total / 57 result) | Jatin Bhatia (58.6% · 128 result) |
| Glen Waverley Hawks Cricket Club | 1,167 | 656 | Ojas Parashar (75.4% · 63 total / 57 result) | Steven Raymond (75.4% · 65 result) |
| Ashwood Cricket Club | 1,002 | 590 | Hugo Fitton (70.4% · 60 total / 54 result) | Kyle Loughnan (69.4% · 62 result) |
| Plenty Cricket Club | 798 | 540 | Greg Wade (76.8% · 68 total / 56 result) | Brad Bond (75.8% · 66 result) |
| Reynella Cricket Club | 829 | 536 | Kristy Rochow (65.8% · 74 total / 73 result) | Jo Cooke (71.3% · 94 result) |
| Georges River Cricket Club | 978 | 619 | Mark Schwartz (85.7% · 88 total / 7 result) | Darren Smith (76.5% · 68 result) |

## Fiji Victorian Cricket Club

- Compared players: 288
- Players where total appearances differ from result-classified matches: 151
- Old Best Win % qualifier basis: Jimmy Sharma at 65.9% using 86 total matches and 82 result-classified matches.
- New Best Win % qualifier basis: Jimmy Sharma at 65.9% using 82 matches with results.
- Example mismatches:
| Player | Total matches | Matches with results | Difference | Win % |
| --- | ---: | ---: | ---: | ---: |
| Kalpeshkumar Patel | 206 | 186 | 20 | 57.0% |
| Deepak Sharma | 157 | 138 | 19 | 30.4% |
| Danny Singh | 335 | 318 | 17 | 49.7% |
| Benjamin Frew | 222 | 209 | 13 | 46.9% |
| Feroz Hassan | 197 | 184 | 13 | 33.2% |

## Southside East Caulfield Cricket Club

- Compared players: 415
- Players where total appearances differ from result-classified matches: 194
- Old Best Win % qualifier basis: Sajan Patel at 61.4% using 63 total matches and 57 result-classified matches.
- New Best Win % qualifier basis: Jatin Bhatia at 58.6% using 128 matches with results.
- Example mismatches:
| Player | Total matches | Matches with results | Difference | Win % |
| --- | ---: | ---: | ---: | ---: |
| Denis Shaw | 228 | 201 | 27 | 48.8% |
| Francis Bernard | 185 | 159 | 26 | 47.8% |
| Christopher Jones | 182 | 165 | 17 | 47.9% |
| Nathan Benson | 129 | 112 | 17 | 39.3% |
| Jatin Dave | 174 | 159 | 15 | 56.0% |

## Glen Waverley Hawks Cricket Club

- Compared players: 1,167
- Players where total appearances differ from result-classified matches: 656
- Old Best Win % qualifier basis: Ojas Parashar at 75.4% using 63 total matches and 57 result-classified matches.
- New Best Win % qualifier basis: Steven Raymond at 75.4% using 65 matches with results.
- Example mismatches:
| Player | Total matches | Matches with results | Difference | Win % |
| --- | ---: | ---: | ---: | ---: |
| Greg Mccormick | 373 | 346 | 27 | 55.8% |
| Chris Briginshaw | 344 | 320 | 24 | 43.1% |
| Brendan Coull | 270 | 247 | 23 | 50.6% |
| James Anderson | 132 | 112 | 20 | 46.4% |
| Chris George | 255 | 237 | 18 | 57.0% |

## Ashwood Cricket Club

- Compared players: 1,002
- Players where total appearances differ from result-classified matches: 590
- Old Best Win % qualifier basis: Hugo Fitton at 70.4% using 60 total matches and 54 result-classified matches.
- New Best Win % qualifier basis: Kyle Loughnan at 69.4% using 62 matches with results.
- Example mismatches:
| Player | Total matches | Matches with results | Difference | Win % |
| --- | ---: | ---: | ---: | ---: |
| Jack Allan Mclean | 81 | 62 | 19 | 51.6% |
| Mark Edmonds | 319 | 302 | 17 | 42.1% |
| Nathan Fitzpatrick | 166 | 150 | 16 | 36.7% |
| Daniel Curnow | 316 | 301 | 15 | 40.5% |
| Matthew Clayton | 189 | 175 | 14 | 45.1% |

## Plenty Cricket Club

- Compared players: 798
- Players where total appearances differ from result-classified matches: 540
- Old Best Win % qualifier basis: Greg Wade at 76.8% using 68 total matches and 56 result-classified matches.
- New Best Win % qualifier basis: Brad Bond at 75.8% using 66 matches with results.
- Example mismatches:
| Player | Total matches | Matches with results | Difference | Win % |
| --- | ---: | ---: | ---: | ---: |
| Jackson Gavin | 231 | 205 | 26 | 53.7% |
| Scott Keane | 200 | 180 | 20 | 50.0% |
| Jayden Bedford | 192 | 173 | 19 | 55.5% |
| Dwayne Fowles | 222 | 204 | 18 | 45.6% |
| Matt Deligiorgis | 207 | 190 | 17 | 57.4% |

## Reynella Cricket Club

- Compared players: 829
- Players where total appearances differ from result-classified matches: 536
- Old Best Win % qualifier basis: Kristy Rochow at 65.8% using 74 total matches and 73 result-classified matches.
- New Best Win % qualifier basis: Jo Cooke at 71.3% using 94 matches with results.
- Example mismatches:
| Player | Total matches | Matches with results | Difference | Win % |
| --- | ---: | ---: | ---: | ---: |
| Matt Connors | 73 | 40 | 33 | 35.0% |
| Greg Hanks | 70 | 39 | 31 | 48.7% |
| Ashton Steinmuller | 42 | 12 | 30 | 41.7% |
| Kye Steinmuller | 41 | 12 | 29 | 41.7% |
| Kaden Pannach | 52 | 26 | 26 | 50.0% |

## Georges River Cricket Club

- Compared players: 978
- Players where total appearances differ from result-classified matches: 619
- Old Best Win % qualifier basis: Mark Schwartz at 85.7% using 88 total matches and 7 result-classified matches.
- New Best Win % qualifier basis: Darren Smith at 76.5% using 68 matches with results.
- Example mismatches:
| Player | Total matches | Matches with results | Difference | Win % |
| --- | ---: | ---: | ---: | ---: |
| Paul Thomas | 580 | 205 | 375 | 55.6% |
| Peter Remfrey | 349 | 76 | 273 | 68.4% |
| Kevin Croom | 419 | 166 | 253 | 48.8% |
| Bruce Whitehouse | 266 | 39 | 227 | 28.2% |
| Martin Cole | 251 | 40 | 211 | 80.0% |

## Jimmy Sharma example

- Before wording change: `54 wins from 82 matches` beside a Detailed Records row showing `Matches = 86` and `Win % = 65.9%`.
- After wording change: `54 wins from 82 matches with results` while Detailed Records still shows `Matches = 86` and `Win % = 65.9%`.
- This makes the denominator distinction explicit without changing the percentage calculation.

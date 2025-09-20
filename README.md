# High School Sports

Scores and Elo for MA high school sports

## Overview

This project is able to create and then do daily updates of
Massachusetts high school sports teams, creating logs of matchups with
scores, and then using the scores to do Elo ratings of the teams by
sport.

## Data Source

The data comes from calls to API URLs like the following:

* https://www.bostonglobe.com/partners/data-high-school-sports-services/prd/202526/v2/scoreboard/2025-09-20.json

There is a sample data file in `data/2025-09-20.json`. The JSON data
has the following structure:

```
{
  "date": "2025-09-20",
  "dates": [
    {
      "date": "2025-09-10",
      "sports": [
        {
          "id": 54,
          "name": "field hockey",
          "gender": 2,
          "season": "fall",
          "games": [
            {
              "id": 48604,
              "date": "2025-09-10",
              "homeConference": "Bay State",
              "visitorConference": "Bay State",
              "tourneyName": null,
              "tourneyLevel": null,
              "time": "4:00 P.M.",
              "label": "",
              "status": "FINAL",
              "teams": {
                "visitor": {
                  "id": 4279,
                  "teamPageUrl": "https://www.bostonglobe.com/sports/high-schools/schedule?sport=field-hockey&school=newton-north",
                  "name": "Newton North",
                  "score": "0",
                  "tracked": "1",
                  "outcome": "0"
                },
                "home": {
                  "id": 4059,
                  "teamPageUrl": "https://www.bostonglobe.com/sports/high-schools/schedule?sport=field-hockey&school=brookline",
                  "name": "Brookline",
                  "score": "3",
                  "tracked": "1",
                  "outcome": "1"
                }
              },
              "overtime": null,
              "isShootoutWin": 0,
              "gameUrl": null,
              "story": {
                "preview": null,
                "url": null,
                "author": null
              },
              "lastUpdated": 1757556807
            },
            ...
          ]
        },
        ...
      ],
    },
    ...
  ]
}
```
  
There will be a per-sport CSV file int the `data` directory like
`data/field-hockey-2025.csv` that is updated with the game results and
upcoming matchups between the teams.

## Computing Elo

The code in `elo.py` is used to compute per-team Elo ratings based on
the scores in the `data` directory.



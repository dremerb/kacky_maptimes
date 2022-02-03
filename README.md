# Deprecated
This repo was cool and all, but for KK7 we did some clean up and moved to here: https://github.com/dremerb/kk_schedule


# kacky_maptimes
Webtool for KR2 - Check which maps are currently played and when a map will be played again. Also can calculate, at how long it will be until a map gets queued.

# How to use
Well, it's complicated :)
This repo has two "release" branches, depending on the mode KR is played in. `main` branch was developed with 2 Phases, phase 1 had a time limit of 10 min, phase 2 a limit of 20 min. Define dates and time limits in `config.yaml`, start `app.py` and you're good. Data for all servers is automatically pulled from all Servers directly from Kacky server via an API - if that's broken, contact Nick or Kim on Discord.
There is another branch `tryhardphase`. In KR2 a mode was tested, in that maps are distributed over different servers by their difficulty level. Servers also could have different time limits. While I totally could have implemented all the changes in a single script, this had to be hacked in 2 days, so I took the easy route :) Might merge, but is's really if you don't really have the possibility to test the end result.

# Warnings
1. Dockerfile not thoroughly tested. Had it running once, but I don't really use Docker. You'll need to map a port to 5000 in the container.

# Configuration
- `port` Port for the flask server to bind to
- `bind_host` IP to bind on. 0.0.0.0 just binds to all
- `cachetime` How long between querying the KR server for current maps. No need to update on every page load.
- `mapchangetime_s` Servers take some time to load the next map. Basically, have to guess this parameter, as load times are quite random... Time in seconds
- `log_visits` Write a time stamp for every visit of index.html. This does not count searches.
- `visits_logfile` Path to a file, where to store the logged visits. Might require an absolute path.
- `enable_stats_page` Enables a simple visitor graph from the data captured if `log_visits` is `True`. Accessible at /stats. This produces extra load on the server, so use wisely
- `phase1timelimit` (main branch only) Time limit for every map in first phase of KR. Time in minutes.
- `phase2start` (main branch only) Date when second phase starts. German date format (dd/mm/yyyy hh:mm)
- `phase1timelimit` (main branch only) Time limit for every map in second phase of KR. Time in minutes.
- `compend` End-date of KR. German date format (dd/mm/yyyy hh:mm)
- `logtype` Where should logging be done to? To `FILE` or `STDOUT`
- `logfile` Path to file, if `logtype` is set to `FILE`. Might require absolute path.
- `loglevel` Level for Python's `logging` module. Values `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

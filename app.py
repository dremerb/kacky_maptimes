import datetime
import os
import logging
import requests
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import matplotlib.dates as mdates
import yaml
import flask
from flask import Flask
import io

# app = Flask(__name__)
app = Flask("app")
MAPIDS = (0, 1)
SERVERS = {}
MAPS = {}
config = {}
timelimit = 10
logger = None

mapcache = {}


def which_time_is_map_played(timestamp: datetime.datetime, findmapid: int):
    get_mapinfo()
    curmaps = list(map(lambda s: (s["color"], s["mapid"]), SERVERS.values()))
    deltas = []

    for idx, maps in enumerate(curmaps):
        # Server IDs start with 1
        idx = idx + 1
        # how many map changes are needed until map is juked?
        cur_pos_in_playlist = SERVERS[idx]["maplist"].index(maps[1])
        pos_of_search_in_playlist = SERVERS[idx]["maplist"].index(findmapid)
        changes_needed = pos_of_search_in_playlist - cur_pos_in_playlist

        if changes_needed < 0:
            changes_needed += len(SERVERS[idx]["maplist"])
        # subtract 1, so we can land in the middle of the queue time
        # (like timer min 5, when timelimit is 10)
        changes_needed -= 1
        minutes_time_to_juke = SERVERS[idx]["timelimit"] / 2 + \
                               int(changes_needed * (SERVERS[idx]["timelimit"]
                                                     + config["mapchangetime_s"] / 60))
        # date and time, when map is juked next (without compensation of minutes)
        play_time = timestamp + datetime.timedelta(
            minutes=minutes_time_to_juke)
        deltas.append(minutes_time_to_juke)
    return deltas


def minutes_to_hourmin_str(minutes):
    if minutes < 10:
        return f"less than 10 minutes"
    return f"{int(minutes / 60):0>2d} hours {minutes % 60:0>2d} minutes"


def pagedata():
    """
    Prepare most data to show on the page
    :return:
    """
    curtime = datetime.datetime.now()
    curtimestr = f"{curtime.hour:0>2d}:{curtime.minute:0>2d}"
    get_mapinfo()
    curmaps = list(map(lambda s: s["mapid"], SERVERS.values()))
    ttl = datetime.datetime.strptime(config["compend"],
                                     "%d.%m.%Y %H:%M") - curtime
    if ttl.days < 0 or ttl.seconds < 0:
        timeleft = (abs(ttl.days), abs(int(ttl.seconds // 3600)),
                    abs(int(ttl.seconds // 60) % 60), -1)
    else:
        timeleft = (abs(ttl.days), abs(int(ttl.seconds // 3600)),
                    abs(int(ttl.seconds // 60) % 60), 1)
    return curtimestr, curmaps, timeleft


@app.route('/')
def index():
    """
    Called by default
    :return:
    """
    # Log visit (only for counting, no further info). Quite GDPR conform, right?
    with open(config["visits_logfile"], "a") as vf:
        vf.write(datetime.datetime.now().strftime("%d/%m/%y %H:%M"))
        vf.write("\n")

    # Get page data
    curtimestr, curmaps, timeleft = pagedata()
    # Prepare server names
    servernames = list(map(lambda s: s["name"], SERVERS.values()))
    return flask.render_template('index.html',
                                 servs=list(zip(servernames, curmaps)),
                                 curtime=curtimestr,
                                 timeleft=timeleft)


@app.route('/', methods=['POST'])
def on_map_play_search():
    """
    This gets called when a search is performed
    :return:
    """
    curtimestr, curmaps, timeleft = pagedata()
    search_map_id = flask.request.form['map']
    servernames = list(map(lambda s: s["name"], SERVERS.values()))
    # check if input is integer
    try:
        search_map_id = int(search_map_id)
    except ValueError:
        # input is not a integer, return error message
        return flask.render_template('index.html',
                                     servs=list(zip(servernames, curmaps)),
                                     curtime=curtimestr,
                                     searched=True, badinput=True,
                                     timeleft=timeleft)
    # check if input is in current map pool
    if search_map_id < MAPIDS[0] or search_map_id > MAPIDS[1]:
        # not in current map pool
        return flask.render_template('index.html',
                                     servs=list(zip(servernames, curmaps)),
                                     curtime=curtimestr,
                                     searched=True, badinput=True,
                                     timeleft=timeleft)
    # input seems ok, try to find next time map is played
    deltas = which_time_is_map_played(datetime.datetime.now(), search_map_id)
    deltas_str = list(map(lambda d: minutes_to_hourmin_str(d), deltas))

    return flask.render_template('index.html',
                                 servs=list(zip(servernames, curmaps)),
                                 curtime=curtimestr,
                                 searched=True, searchtext=search_map_id,
                                 timeleft=timeleft,
                                 deltas=list(zip(servernames, deltas_str)))


@app.before_first_request
def do_something_only_once():
    global SERVERS, MAPS
    logger.info("Initializing Data")
    with open(os.path.join(os.path.dirname(__file__), "maps.yaml"),
              "r") as mapfile:
        MAPS = yaml.load(mapfile, Loader=yaml.FullLoader)
    # Set SERVERS var
    get_mapinfo()


def get_mapinfo():
    global SERVERS
    # Update SERVERS every minute
    if SERVERS != {}:
        if datetime.datetime.now() - list(SERVERS.values())[0][
            "update"] < datetime.timedelta(seconds=config["cachetime"]):
            # Return if data is not old enough yet
            logger.info("No update for SERVERS needed!")
            return
    logger.info("Updating SERVERS.")
    try:
        krdata = requests.get(
            "https://kackiestkacky.com/api/serverinfo.php").json()
    except ConnectionError:
        logger.error("Could not connect to KR API!")
        flask.render_template('error.html',
                              error="Could not contact KR server. RIP!")
    tmpdict = {}
    for server in krdata.keys():
        d = krdata[server]
        mapid = d["MapName"].split("#")[1]
        serverid = int(d["ServerId"])
        servname = d["ServerName"]
        color = MAPS["server-colors"][str(serverid)]
        tmpdict[serverid] = {"name": servname + " - " + color,
                             "mapid": int(mapid),
                             "update": datetime.datetime.now(),
                             "color": MAPS["server-colors"][str(serverid)],
                             "maplist": MAPS[color]["maps"],
                             "timelimit": MAPS[color]["timelimit"]}
    del SERVERS
    SERVERS = tmpdict.copy()


@app.route('/stats/stats.png')
def stats_generator():
    """
    Build some fancy plots to see site usage
    :return:
    """
    logger.info("Building figure 'stats.png'")
    # Read data
    df = pd.read_csv(config["visits_logfile"], sep=" ")
    df.columns = ["dates", "times"]
    countdatesdf = df.groupby("dates").count()
    counttimesdf = df.groupby("times").count()

    # Create Plot
    fig, (ax, ax2) = plt.subplots(2, 1)

    # first plot
    ax.plot(countdatesdf.index, countdatesdf['times'])
    # Format x ticks
    # Do not use the following lines, as they break stuff. If MPL does this 
    # automatically, it magically starts to work
    # datesFmt = mdates.DateFormatter('%d/%m/%y')
    # ax.xaxis.set_major_formatter(datesFmt)
    ax.set_xticks(countdatesdf.index)
    # plt.xticks(rotation=70)
    ax.tick_params(axis="x", rotation=70)
    ax.set_title("Visits per Day")

    # second plot
    ax2.bar(counttimesdf.index, counttimesdf["dates"])
    # Do not use the following lines, as they break stuff. If MPL does this
    # automatically, it magically starts to work
    # ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    # ax2.set_xticks(counttimesdf.index)
    ax2.xaxis.set_major_locator(plt.MaxNLocator(28))
    ax2.tick_params(axis="x", rotation=70)
    ax2.set_title("Visits by Time of Day")

    plt.tight_layout()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return flask.Response(output.getvalue(), mimetype='image/png')


@app.route('/stats')
def stats():
    if config["enable_stats_page"]:
        return flask.render_template('stats.html')
    else:
        return flask.render_template("error.html", error="Stats page disabled")


if __name__ == '__main__':
    # Reading config file
    with open(os.path.join(os.path.dirname(__file__), "config.yaml"),
              "r") as conffile:
        config = yaml.load(conffile, Loader=yaml.FullLoader)

    MAPIDS = (config["min_mapid"], config["max_mapid"])

    # Set up logging
    logger = logging.getLogger("KRmaptimes")
    logger.setLevel(eval("logging." + config["loglevel"]))

    if config["logtype"] == "STDOUT":
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # YES, this totally ignores threadsafety. On the other hand, it is quite safe to assume that it only will
    # occur very rarely that things get logged at the same time in this usecase.
    # Furthermore, logging is absolutely not critical in this case and mostly used for debugging. As long as the
    # SQLite DB doesn't break, we're safe!
    elif config["logtype"] == "FILE":
        config["logfile"] = config["logfile"].replace("~", os.getenv("HOME"))
        if not os.path.dirname(config["logfile"]) == "" and not os.path.exists(
                os.path.dirname(config["logfile"])):
            os.mkdir(os.path.dirname(config["logfile"]))
        f = open(config["logfile"], "w+")
        f.close()
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            filename=config["logfile"])
    else:
        print("ERROR: Logging not correctly configured!")
        exit(1)

    if config["log_visits"]:
        # Enable logging of visitors to dedicated file. More comfortable than using system log to count visitors.
        # Counting with "cat visits.log | wc -l"
        f = open(config["visits_logfile"], "a+")
        f.close()

    logger.info("Starting application.")
    app.run(host=config["bind_hosts"], port=config["port"])

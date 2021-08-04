import datetime
import os
import logging
import requests

import yaml
import flask
from flask import Flask

app = Flask(__name__)
MAPIDS = (76, 150)
SERVERS = {}
config = {}
timelimit = 10
logger = None

mapcache = {}

def which_time_is_map_played(timestamp: datetime.datetime, findmapid: int):
    get_mapinfo()
    curmaps = list(map(lambda s: s["mapid"], SERVERS.values()))
    deltas = []
    for idx, serv in enumerate(curmaps):
        # how many map changes are needed until map is juked?
        changes_needed = findmapid - serv
        if changes_needed < 0:
            changes_needed += MAPIDS[1] - MAPIDS[0]
        minutes_time_to_juke = int(changes_needed * (timelimit + config["mapchangetime_s"] / 60))
        # date and time, when map is juked next (without compensation of minutes)
        play_time = timestamp + datetime.timedelta(minutes=minutes_time_to_juke)
        deltas.append(minutes_time_to_juke)
    return deltas


def minutes_to_hourmin_str(minutes):
    if minutes < 10:
        return f"less than 10 minutes"
    return f"{int(minutes/60):0>2d} hours {minutes%60:0>2d} minutes"


def pagedata():
    """
    Prepare most data to show on the page
    :return:
    """
    curtime = datetime.datetime.now()
    curtimestr = f"{curtime.hour:0>2d}:{curtime.minute:0>2d}"
    # TODO: Adjust this, so that it works with phase 2
    # TODO: Rework this completely, currently not featured in prod
    if int(curtime.minute / 10) == 5:
        nextmaptimestr = f"{curtime.hour + 1:0>2d}:00"
    else:
        nextmaptimestr = f"{curtime.hour:0>2d}:{(curtime.minute // 10 + 1) * 10:0>2d}"
    get_mapinfo()
    curmaps = list(map(lambda s: s["mapid"], SERVERS.values()))
    ttl = datetime.datetime.strptime(config["compend"], "%d.%m.%Y %H:%M") - curtime
    if ttl.days < 0 or ttl.seconds < 0:
        timeleft = (abs(ttl.days), abs(int(ttl.seconds // 3600)),  abs(int(ttl.seconds // 60) % 60), -1)
    else:
        timeleft = (abs(ttl.days), abs(int(ttl.seconds // 3600)),  abs(int(ttl.seconds // 60) % 60), 1)
    # TODO: nextmaptime needs to be adjusted with start times
    return curtimestr, nextmaptimestr, curmaps, timeleft


@app.route('/')
def index():
    """
    Called by default
    :return:
    """
    curtimestr, nextmaptimestr, curmaps, timeleft = pagedata()
    servernames = list(map(lambda s: s["name"], SERVERS.values()))
    return flask.render_template('index.html', servs=list(zip(servernames, curmaps)), curtime=curtimestr,
                                 nextmaptime=nextmaptimestr, timeleft=timeleft)


@app.route('/', methods=['POST'])
def on_map_play_search():
    """
    This gets called when a search is performed
    :return:
    """
    curtimestr, nextmaptimestr, curmaps, timeleft = pagedata()
    search_map_id = flask.request.form['map']
    servernames = list(map(lambda s: s["name"], SERVERS.values()))
    # check if input is integer
    try:
        search_map_id = int(search_map_id)
    except ValueError:
        # input is not a integer, return error message
        return flask.render_template('index.html', servs=list(zip(servernames, curmaps)), curtime=curtimestr,
                                     nextmaptime=nextmaptimestr, searched=True, badinput=True, timeleft=timeleft)
    # check if input is in current map pool
    if search_map_id < MAPIDS[0] or search_map_id > MAPIDS[1]:
        # not in current map pool
        return flask.render_template('index.html', servs=list(zip(servernames, curmaps)), curtime=curtimestr,
                                     nextmaptime=nextmaptimestr, searched=True, badinput=True, timeleft=timeleft)
    # input seems ok, try to find next time map is played
    deltas = which_time_is_map_played(datetime.datetime.now(), search_map_id)
    deltas_str = list(map(lambda d: minutes_to_hourmin_str(d), deltas))

    return flask.render_template('index.html', servs=list(zip(servernames, curmaps)), curtime=curtimestr,
                                 nextmaptime=nextmaptimestr, searched=True, searchtext=search_map_id, timeleft=timeleft,
                                 deltas=list(zip(servernames, deltas_str)))


@app.before_first_request
def do_something_only_once():
    global SERVERS, config, timelimit
    logger.info("Initializing Data")
    with open(os.path.join(os.path.dirname(__file__), "config.yaml"), "r") as conffile:
        config = yaml.load(conffile, Loader=yaml.FullLoader)
    # Set SERVERS var
    get_mapinfo()
    # check if we are in phase 2
    # TODO: FIX, this has to be checked somewhere else!
    if datetime.datetime.now() > datetime.datetime.strptime(config["phase2start"], "%d.%m.%Y %H:%M"):
        timelimit = config["phase2timelimit"]
    else:
        timelimit = config["phase1timelimit"]


def get_mapinfo():
    global SERVERS

    # Update SERVERS every minute
    if SERVERS != {}:
        if list(SERVERS.values())[0]["update"] < datetime.datetime.now() + datetime.timedelta(minutes=1.0):
            # Return if data is not old enough yet
            logger.info("No update for SERVERS needed!")
            return
    logger.info("Updating SERVERS.")
    try:
        krdata = requests.get("https://kackiestkacky.com/api/serverinfo.php").json()
    except ConnectionError:
        flask.render_template('error.html', error="Could not contact KR server. RIP!")
    tmpdict = {}
    for server in krdata.keys():
        d = krdata[server]
        mapid = d["MapName"].split("#")[1]
        serverid = d["ServerId"]
        servname = d["ServerName"]
        tmpdict[serverid] = {"name": servname, "mapid": int(mapid), "update": datetime.datetime.now()}
    del SERVERS
    SERVERS = tmpdict.copy()


if __name__ == '__main__':
    logger = logging.getLogger("KRmaptimes")
    logger.info("Starting application.")
    app.run(host="0.0.0.0", port=5005)
    #app.run()

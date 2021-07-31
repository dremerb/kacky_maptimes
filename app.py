import datetime
import os

import yaml
import flask
from flask import Flask

app = Flask(__name__)
MAPIDS = (76, 150)
SERVERS = {}
config = {}
timelimit = 10


def which_time_is_map_played(timestamp: datetime.datetime, findmapid: int):
    curmaps = which_map_is_cur_played(timestamp)
    deltas = []
    for idx, serv in enumerate(curmaps):
        # how many map changes are needed until map is juked?
        changes_needed = abs(serv - findmapid)
        minutes_time_to_juke = int(changes_needed * (timelimit + config["mapchangetime_s"] / 60))
        # date and time, when map is juked next (without compensation of minutes)
        play_time = timestamp + datetime.timedelta(minutes=minutes_time_to_juke)
        deltas.append(minutes_time_to_juke)
    return deltas


def minutes_to_hourmin_str(minutes):
    return f"{int(minutes/60):0>2d} hours {minutes%60:0>2d} minutes"


def which_map_is_cur_played(timestamp: datetime.datetime):
    """
    Calculates the map that is played at the given timestamp
    :param timestamp: Timestamp for that shall be determined which map is playing
    :return: list that contains map played at given timestamp
    """
    res = []
    # Get number of map changes since last known map on server
    for serv in SERVERS.values():
        n_changes = int((timestamp - serv["timestamp"]).total_seconds() / 60 / timelimit)
        # adjust for time lost in map loading
        #                 sec lost in maploading
        adjust_fact = (n_changes * config["mapchangetime_s"]) // timelimit // 60
        new_id = serv["map"] + ((n_changes - adjust_fact) % (MAPIDS[1] + 1 - MAPIDS[0]))
        res.append(new_id)
    return res


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
    curmaps = which_map_is_cur_played(curtime)
    ttl = datetime.datetime.strptime(config["compend"], "%d.%m.%Y %H:%M") - curtime
    if ttl.days < 0 or ttl.seconds < 0:
        timeleft = f"Competition over since {abs(ttl.days)} days, {abs(ttl.seconds) // 3600:0>2d} hours and " \
                   f"{(abs(ttl.seconds) // 60) % 60:0>2d} minutes."
    else:
        timeleft = f"Competition ends in {abs(ttl.days)} days, {abs(ttl.seconds) // 3600:0>2d} hours and " \
                   f"{(abs(ttl.seconds) // 60) % 60:0>2d} minutes."
    # TODO: nextmaptime needs to be adjusted with start times
    return curtimestr, nextmaptimestr, curmaps, timeleft


@app.route('/')
def index():
    """
    Called by default
    :return:
    """
    curtimestr, nextmaptimestr, curmaps, timeleft = pagedata()
    return flask.render_template('index.html', servs=list(zip(SERVERS.keys(), curmaps)), curtime=curtimestr,
                                 nextmaptime=nextmaptimestr, timeleft=timeleft)


@app.route('/', methods=['POST'])
def on_map_play_search():
    """
    This gets called when a search is performed
    :return:
    """
    curtimestr, nextmaptimestr, curmaps, timeleft = pagedata()
    search_map_id = flask.request.form['map']
    # check if input is integer
    try:
        search_map_id = int(search_map_id)
    except ValueError:
        # input is not a integer, return error message
        return flask.render_template('index.html', servs=list(zip(SERVERS.keys(), curmaps)), curtime=curtimestr,
                                     nextmaptime=nextmaptimestr, searched=True, badinput=True, timeleft=timeleft)
    # check if input is in current map pool
    if search_map_id < MAPIDS[0] or search_map_id > MAPIDS[1]:
        # not in current map pool
        return flask.render_template('index.html', servs=list(zip(SERVERS.keys(), curmaps)), curtime=curtimestr,
                                     nextmaptime=nextmaptimestr, searched=True, badinput=True)
    # input seems ok, try to find next time map is played
    deltas = which_time_is_map_played(datetime.datetime.now(), search_map_id)
    deltas_str = list(map(lambda d: minutes_to_hourmin_str(d), deltas))

    return flask.render_template('index.html', servs=list(zip(SERVERS.keys(), curmaps)), curtime=curtimestr,
                                 nextmaptime=nextmaptimestr, searched=True, searchtext=search_map_id,
                                 deltas=list(zip(SERVERS.keys(), deltas_str)))



@app.before_first_request
def do_something_only_once():
    global SERVERS, config, timelimit
    if os.path.isfile("servers.yaml"):
        with open("servers.yaml", "r") as yamlfile:
            SERVERS = yaml.load(yamlfile, Loader=yaml.FullLoader)
    else:
        SERVERS[f"Server 1"] = {"timestamp": datetime.datetime.now(), "map": 76}
    with open("config.yaml", "r") as conffile:
        config = yaml.load(conffile, Loader=yaml.FullLoader)
    # check if we are in phase 2
    if datetime.datetime.now() > datetime.datetime.strptime(config["phase2start"], "%d.%m.%Y %H:%M"):
        timelimit = config["phase2timelimit"]
    else:
        timelimit = config["phase1timelimit"]


@app.route('/manage')
def manage_servers():
    dates = []
    times = []
    maps = []
    for serv in SERVERS.values():
        dates.append(serv["timestamp"].strftime("%d.%m.%Y"))
        times.append(serv["timestamp"].strftime("%H:%M"))
        maps.append(serv["map"])
    # we need UIDs for the text field names (+1 because first col is constant hardcoded string
    ids = list(range(len(SERVERS.keys())))
    dates = zip(ids, dates)
    times = zip(ids, times)
    maps = zip(ids, maps)
    return flask.render_template('manage.html', servs=SERVERS.keys(), dates=dates, times=times, maps=maps)


@app.route('/manage', methods=['POST'])
def manage_action():
    global SERVERS
    if flask.request.form["passwd"] != config["adminpwd"]:
        return flask.render_template('error.html', error="Bad Password!")
    if 'del_serv' in flask.request.form:
        # We want to remove a server. Get server name by truncating "Remove " from button value.
        serv_name = flask.request.form["del_serv"][7:]
        SERVERS.pop(serv_name)
        # Server names might have inconsistent indexes, fix that
        servers_tmp = {}
        for idx, serv in enumerate(SERVERS.keys()):
            print(f"Renaming '{serv}' to 'Server {idx}'")
            servers_tmp[f"Server {idx+1}"] = SERVERS[serv]
        SERVERS = servers_tmp
    if 'add_serv' in flask.request.form:
        # Adding a new server to the SERVERS dict. Keys are sorted by ascending IDs, therefore just check last entry
        # for ID and increment
        new_index = int(list(SERVERS.keys())[len(SERVERS.keys())-1].split(" ")[1])
        SERVERS[f"Server {new_index+1}"] = {"timestamp": datetime.datetime.now(), "map": 76}
    if "save" in flask.request.form:
        # Read all fields and store them in SERVERS dict
        for idx, serv in enumerate(SERVERS.keys()):
            # Read all fields
            date = flask.request.form[f"date{idx}"]
            time = flask.request.form[f"time{idx}"]
            # Check if they are in correct format
            try:
                map = int(flask.request.form[f"map{idx}"])
            except ValueError:
                return flask.render_template('error.html', error="Faulty input for map! Try again!")
            if map < MAPIDS[0] or map > MAPIDS[1]:
                return flask.render_template('error.html', error="Faulty input for map! Try again!")
            try:
                timestamp = datetime.datetime.strptime(f"{date} {time}", "%d.%m.%Y %H:%M")
            except ValueError:
                return flask.render_template('error.html', error="Faulty input for time or date! Try again!")
            # Set SERVERS
            SERVERS[serv] = {"timestamp": timestamp, "map": map}
        # Dump SERVERS dict, so it can be reloaded
        with open("servers.yaml", "w+") as yamlfile:
            yaml.dump(SERVERS, yamlfile, default_flow_style=False)
    return flask.redirect('manage')


if __name__ == '__main__':
    app.run()

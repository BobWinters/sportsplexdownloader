from qbittorrentapi import Client
import schedule
import time
from bs4 import BeautifulSoup
import requests
import os
import json
import shutil
import re
import datefinder
import requests
from datetime import datetime, timedelta
from pytz import timezone
import time
import logging
import os.path
import lxml


Log_Format = "%(levelname)s %(asctime)s - %(message)s"

seasonyear = "2122"
nbaseasonyear = "2021-22"
nbaschedule = os.path.join(os.getcwd(), "nbaschedule.json")
configpath = os.path.join(os.getcwd(), "config.cfg")
loggingpath = os.path.join(os.getcwd(), "logfile.log")
pathtorrenttitle = os.path.join(os.getcwd(), "torrenttitle.cfg")
pathcompletedtorrents = os.path.join(os.getcwd(), "CompletedTorrents.cfg")

logging.basicConfig(filename=loggingpath,
                    filemode="w",
                    format=Log_Format,
                    level=logging.INFO)

logger = logging.getLogger()

try:
    with open(configpath, "r") as fp:
        configjson = json.loads(fp.read())
except Exception as inst:
    logger.error("Error, unable to find " + configpath + inst)
    quit()

try:
    with open(nbaschedule, "r") as fp:
        nbaschedulejson = json.loads(fp.read())
except Exception as inst:
    logger.error("Error, unable to find " + nbaschedule + inst)
    quit()

try:
    with open(pathcompletedtorrents, "r") as fp:
        completedtorrents = json.loads(fp.read())
except Exception as inst:
    logger.warning("No completed torrents " + str(inst))
    completedtorrents = []


try:
    with open(pathtorrenttitle, "r") as fp:
        torrenttitle = json.loads(fp.read())
except Exception as inst:
    logger.warning("No torrenttitle " + str(inst))
    torrenttitle = []


def finddateinschedule(aawayteam, ahometeam, acurrentdate):
    startdate = acurrentdate.date() - timedelta(days=1)
    startdateformatted = startdate.strftime("%Y-%m-%d")
    enddate = acurrentdate.date() + timedelta(days=1)
    enddateformatted = enddate.strftime("%Y-%m-%d")
    currentdateformatted = acurrentdate.strftime("%Y-%m-%d")
    datelist = [startdateformatted, currentdateformatted, enddateformatted]

    for amonthcollection in nbaschedulejson["lscd"]:
        for agamecollection in amonthcollection["mscd"]["g"]:
            if agamecollection["gdte"] in datelist and agamecollection["h"]["ta"] == aawayteam["keywords"][1] and agamecollection["v"]["ta"] == ahometeam["keywords"][1]:
                return agamecollection["etm"]
    logger.error("Can't find in schedule: Away team = " + aawayteam["keywords"][1] + "Home team = " + ahometeam["keywords"][1] + " Startdate: " +
                  startdateformatted + " Enddate: " + enddateformatted)
    return ""


def generatefilename(ahometeam, aawayteam, date):
    eastern = timezone('US/Eastern')
    utc = timezone('UTC')
    gamedatefound = eastern.localize(list(datefinder.find_dates(date))[0])

    formatted_date = gamedatefound.astimezone(utc).strftime("%Y-%m-%d")

    logger.info("Fixed Name: " + "NBA " + formatted_date + " " + ahometeam + " vs " + aawayteam)
    return "NBA " + formatted_date + " " + ahometeam + " vs " + aawayteam


def fixfilename(filename):
    hometeam = findteaminfilename(filename, True)
    if hometeam == "":
        return ""

    awayteam = findteaminfilename(filename, False)
    if awayteam == "":
        return ""

    currentdate = finddateinfilename(filename)
    if currentdate == "":
        return ""

    correcteddate = finddateinschedule(awayteam, hometeam, currentdate)
    if correcteddate == "":
        return ""

    return generatefilename(awayteam['teamname'], hometeam['teamname'], correcteddate)


def findteaminfilename(filename, isaway):
    for myteam in configjson['teams']:
        for myteamkeywords in myteam['keywords']:
            regteamtext = ""
            if isaway:
                regteamtext = myteamkeywords + '@'
            else:
                regteamtext = '@' + myteamkeywords
            regteam = re.search(regteamtext, filename, flags=re.IGNORECASE)
            if regteam:
                logger.info("Found Team: " + myteam['keywords'][0] + " in " + filename)
                return myteam

    logger.error("Can't find team, Away is " + str(isaway) + " " + filename)
    return ""


def finddateinfilename(filename):
    matches = list(datefinder.find_dates(re.sub(r'[^a-zA-Z0-9\n\.]', ' ', filename)))
    if len(matches) > 0:
        logger.info("Found Date: " + matches[0].strftime("%Y-%m-%d") + " in " + filename)
        return matches[0]
    else:
        logger.error("Can't find date: " + filename)
        return ""


def checktorrents():
    torrentlist = client.torrents_info(status_filter=None, category=configjson["generalsettings"]["qbitorrentlabel"],
                                       sort=None, reverse=None, limit=None, offset=None,
                                       torrent_hashes=None, tag=None)
    for atorrent in torrentlist:
        if atorrent.state == "uploading" or atorrent.state == "stalledUP" or atorrent.state == "pausedUP":
            if atorrent.hash not in completedtorrents:
                for afile in atorrent.files:

                    newfilename = fixfilename(afile.name)
                    if newfilename == "":
                        continue
                    filenamewithext = os.path.basename(atorrent.save_path + "/" + afile.name)
                    filename, ext = os.path.splitext(filenamewithext)

                    logger.info("Copying: Source = " + atorrent.save_path + "/" + afile.name + " Destination = /mnt/local/Media/Sports/NBA/Season " + seasonyear + "/" + newfilename + ext)
                    try:
                        shutil.copy(atorrent.save_path + "/" + afile.name, "/mnt/local/Media/Sports/NBA/Season " + seasonyear + "/" + newfilename + ext)
                    except Exception as insti:
                        logger.error("Fatal error copying file:" + "Copying: Source = " + atorrent.save_path + afile.name + " Destination = " + configjson["generalsettings"]["finalpath"] + "Season " + seasonyear + "/" + newfilename + ext + " " + insti)
                        quit()
                    try:
                        plex_autoscanheaders = {'Content-Type': 'application/x-www-form-urlencoded'}
                        requests.post(configjson["generalsettings"]["plexautoscanurl"], data="eventType=Manual&filepath=" + configjson["generalsettings"]["finalpath"] + "Season " + seasonyear + "/", headers=plex_autoscanheaders)
                    except Exception as insti:
                        logger.error("Error connecting to Plex_Autoscan file:" + configjson["generalsettings"]["plexautoscanurl"] + "eventType=Manual&filepath=" + configjson["generalsettings"]["finalpath"] + "Season " + seasonyear + "/")

                logger.info("Adding hash to completedtorrents: " + atorrent.hash)
                completedtorrents.append(atorrent.hash)
                with open(pathcompletedtorrents, "w") as outputfile:
                    json.dump(completedtorrents, outputfile)
        if atorrent.state == "pausedUP" and atorrent.hash in completedtorrents:
            logger.info("Deleting Torrent: " + atorrent.name)
            atorrent.delete(delete_files=True)
            if atorrent.hash in completedtorrents:
                completedtorrents.remove(atorrent.hash)
            with open(pathcompletedtorrents, "w") as outputfile:
                json.dump(completedtorrents, outputfile)


def checkrss():
    page_link = configjson["generalsettings"]["jacketturl"]
    try:
        logger.info("Getting jackett webpage")
        page_response = requests.get(page_link, timeout=10)
    except Exception as insti:
        logger.error("Error: Unable to contact Jackett" + insti)

    page_content = BeautifulSoup(page_response.content, "xml")
    foundnew = False
    for torrentItem in page_content.findAll('item'):
        atitle = torrentItem.find('title').text
        for teamtoget in configjson["teams"]:
            if teamtoget["download"] and teamtoget["teamname"].casefold() in atitle.casefold():
                alink = torrentItem.find('link').text
                if atitle not in torrenttitle:
                    torrenttitle.append(atitle)
                    foundnew = True
                    client.torrents_add(
                        urls=alink
                        , torrent_files=None, save_path=None, cookie=None, category=configjson["generalsettings"]["qbitorrentlabel"], is_skip_checking=None,
                        is_paused=None, is_root_folder=None, rename=None, upload_limit=None, download_limit=None,
                        use_auto_torrent_management=None, is_sequential_download=None, is_first_last_piece_priority=None,
                        tags=None, content_layout=None, ratio_limit=None, seeding_time_limit=configjson["generalsettings"]["seeding_time_limit"], download_path=None,
                        use_download_path=None)
                logger.info("Already have: " + atitle)
    if foundnew is True:
        with open(pathtorrenttitle, "w") as outputfile:
            json.dump(torrenttitle, outputfile)


schedule.every(configjson["generalsettings"]["checktorrentinterval"]).seconds.do(checktorrents)
schedule.every(configjson["generalsettings"]["checkrssinterval"]).seconds.do(checkrss)


client = Client(host=configjson["generalsettings"]["qbitorrenturl"],
                username=configjson["generalsettings"]["qbitorrentusername"],
                password=configjson["generalsettings"]["qbitorrentpassword"])


checktorrents()
checkrss()

while 1:
    n = schedule.idle_seconds()
    if n is None:
        break
    elif n > 0:
        time.sleep(n)
    schedule.run_pending()

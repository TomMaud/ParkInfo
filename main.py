import time, requests, random
from bs4 import BeautifulSoup, SoupStrainer
import lxml, threading
import sqlite3
import re
from SearchModule import *
from Tracker import *

requests_session = requests.Session()

RCDB = 'https://rcdb.com'
lastparkid = 0
skips = 0


def createDatabaseandTables():
    conn = sqlite3.connect('ParkDatabase.db')
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Park (
            ParkID       INTEGER PRIMARY KEY,
            ParkName     TEXT NOT NULL,
            ParkLocation TEXT NOT NULL,
            ParkStatus   TEXT NOT NULL,
            RCDBURL      TEXT,
            DRDBURL      TEXT,
            Operator     TEXT,
            ParkOpened   TEXT,
            ParkClosed   TEXT
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS Coaster (
            CoasterURL    TEXT PRIMARY KEY,
            CoasterName   TEXT NOT NULL,
            CoasterOpened TEXT,
            CoasterClosed TEXT,
            CoasterDesign TEXT,
            CoasterType   TEXT,
            CoasterStatus TEXT,
            Manufacturer TEXT,
            CoasterParkID INTEGER NOT NULL,
            FOREIGN KEY (CoasterParkID) REFERENCES Park(ParkID)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS DarkRide (
            DarkRideURL    TEXT PRIMARY KEY,
            DarkRideName   TEXT NOT NULL,
            DarkRideType   TEXT NOT NULL,
            DarkRideOpened TEXT,
            DarkRideClosed TEXT,
            DarkRideStatus TEXT,
            DarkRideParkID INTEGER NOT NULL,
            FOREIGN KEY (DarkRideParkID) REFERENCES Park(ParkID)
        )
    ''')

    conn.commit()
    conn.close()


def cleaner(value):
    return None if value is None or value.strip() in ("", "-") else value


def AddRCDBPark(Name, location, Status, RCDBURL, ParkOpened, ParkClosed):
    global lastparkid
    conn = sqlite3.connect('ParkDatabase.db')
    if conn.execute("SELECT 1 FROM Park WHERE RCDBURL = ?", (RCDBURL,)).fetchone():
        conn.close()
        return False
    lastparkid += 1
    conn.execute(
        "INSERT INTO Park (ParkID, ParkName, ParkLocation, ParkStatus, RCDBURL, DRDBURL, Operator, ParkOpened, ParkClosed) "
        "VALUES (?,?,?,?,?,NULL,NULL,?,?)",
        (lastparkid, Name, location or "Unknown", Status or "Unknown", RCDBURL, ParkOpened, ParkClosed))
    conn.commit()
    conn.close()


def AddDRDB(Name, location, Status, DRDBURL, ParkOpened, ParkClosed, Operator):
    global lastparkid
    conn = sqlite3.connect('ParkDatabase.db')
    if conn.execute("SELECT 1 FROM Park WHERE DRDBURL = ?", (DRDBURL,)).fetchone():
        conn.close()
        return False
    lastparkid += 1
    conn.execute(
        "INSERT INTO Park (ParkID, ParkName, ParkLocation, ParkStatus, RCDBURL, DRDBURL, Operator, ParkOpened, ParkClosed) "
        "VALUES (?,?,?,?,NULL,?,?,?,?)",
        (lastparkid, Name, location or "Unknown", Status or "Unknown", DRDBURL, Operator, ParkOpened, ParkClosed))
    conn.commit()
    conn.close()


def updateDRDBPark(DRDBURL, Operator, ParkID):
    conn = sqlite3.connect('ParkDatabase.db')
    conn.execute("UPDATE Park SET DRDBURL=?, Operator=? WHERE ParkID=?", (DRDBURL, Operator, ParkID))
    conn.commit()
    conn.close()


def addCoaster(URL, Name, Opened, Closed, Design, Type, Status, ParkID):
    conn = sqlite3.connect('ParkDatabase.db')
    conn.execute('INSERT OR REPLACE INTO Coaster VALUES (?, ?, ?, ?, ?, ?, ?,NULL, ?)',
                 (URL, Name, Opened, Closed, Design, Type, Status, ParkID))
    conn.commit()
    conn.close()


def addDarkRide(URL, Name, Type, Opened, Closed, Status, ParkID):
    conn = sqlite3.connect('ParkDatabase.db')
    conn.execute('INSERT OR REPLACE INTO DarkRide VALUES (?, ?, ?, ?, ?, ?, ?)',
                 (URL, Name, Type or "Unknown", Opened, Closed, Status, ParkID))
    conn.commit()
    conn.close()


def checkduplicates(park, address):
    try:
        x = requests.get(f'https://rcdb.com/r.htm?nc={park}&ot=3')
        soup = BeautifulSoup(x.text, 'lxml', parse_only=SoupStrainer(["tr"]))
        div_blocks = soup.find_all('tr')
        div_blocks = div_blocks[4:]
        sameselection = None
        selectionsimscheck = 0
        for selection in div_blocks:
            simscheck = 0
            cells = selection.find_all('td')
            location = cells[2].text.lower()
            for i in address:
                if i in location:
                    simscheck += 1
            if simscheck > selectionsimscheck:
                selectionsimscheck = simscheck
                sameselection = selection
        if selectionsimscheck > 1:
            cells = sameselection.find_all('td')
            name = cells[1].text
            url = RCDB + cells[1].find("a").attrs['href']
            location = cells[2].text
            try:
                status = cells[3].text
            except:
                status = None
            try:
                opening = cells[4].find_all("time")
                opened = opening[0].attrs["datetime"].split("-")[0]
                if len(opening) > 1:
                    closed = opening[1].attrs["datetime"].split("-")[0]
                else:
                    closed = None
            except:
                opened = None
                closed = None
            conn = sqlite3.connect('ParkDatabase.db')
            if not conn.execute("SELECT 1 FROM Park WHERE RCDBURL = ?", (url,)).fetchone():
                AddRCDBPark(name, location, status, url, opened, closed)
            value = conn.execute("SELECT ParkID FROM Park WHERE RCDBURL = ?", (url,)).fetchone()[0]
            conn.close()
            return value

    except IndexError:
        print("No page")
        return None


def darkridelistings(pagenum, kinds=("rides",)):
    r = requests_session.get(f"https://darkridedatabase.com/job_listing-sitemap{pagenum}.xml")
    for u in BeautifulSoup(r.text, "xml").find_all("url"):
        loc = u.find("loc").text
        kind = loc.removeprefix("https://darkridedatabase.com/").split("/")[0]
        if kind in kinds:
            darkridepage(loc)

def darkrideparklistings(pagenum, kinds=("park",)):
    r = requests_session.get(f"https://darkridedatabase.com/job_listing-sitemap{pagenum}.xml")
    for u in BeautifulSoup(r.text, "xml").find_all("url"):
        loc = u.find("loc").text
        kind = loc.removeprefix("https://darkridedatabase.com/").split("/")[0]
        if kind in kinds:
            darkrideparkpage(loc)

def darkridepage(page):
    global skips
    try:
        x = requests_session.get(page)
        soup = BeautifulSoup(x.text, 'lxml')

        name = soup.find("h1").text.strip()

        info = {}
        heading = soup.find("h5", string=re.compile("General info"))
        for li in heading.find_all_next("li"):
            if li.find_previous("h5") != heading:
                break
            parts = list(li.stripped_strings)
            if len(parts) >= 2:
                info[parts[0].lower()] = " ".join(parts[1:])

        type = info.get("type")
        status = info.get("status")
        opened = info.get("opened")
        closed = next((v for k, v in info.items() if "clos" in k), None)

        park_heading = soup.find("h5", string=re.compile("Park"))
        parkobject = park_heading.find_next("a")
        park = parkobject.text.strip()
        parkurl = parkobject.attrs["href"]
        conn = sqlite3.connect('ParkDatabase.db')
        row = conn.execute("SELECT ParkID FROM Park WHERE DRDBURL = ?", (parkurl,)).fetchone()
        conn.close()
        if row is None:
            if skips < 1:
                darkrideparkpage(parkurl)
                return darkridepage(page)
            else:
                skips = 0
                return Exception(AttributeError)
        addDarkRide(page, name, type, opened, closed, status, row[0])

    except IndexError:
        print("No page")
    except AttributeError:
        print("No page at "+page)



def darkrideparkpage(url):
    global skips
    x = requests_session.get(url, timeout=10)
    soup = BeautifulSoup(x.text, 'lxml')

    name = soup.find("h1").text.strip()

    info = {}
    heading = soup.find("h5", string=re.compile("General info"))
    for el in heading.next_elements:
        if getattr(el, "name", None) == "h5":
            break
        if getattr(el, "name", None) == "li":
            parts = list(el.stripped_strings)
            if len(parts) >= 2:
                info[parts[0].lower()] = " ".join(parts[1:])

    operator = info.get("operator")
    status = info.get("status")
    opened = info.get("opened")
    closed = next((v for k, v in info.items() if "clos" in k), None)
    try:

        heading = soup.find("h5", string=re.compile("Location"))
        address = (list(heading.next_elements)[4].text.lower().replace(",", "").strip().split("\n")[0].split(" "))
        y = checkduplicates(name, address)
        if y:
            updateDRDBPark(url, operator, y)
        else:
            AddDRDB(name, " ".join(address), status, url, opened, closed, operator)
    except:
        print("Skipping", url)
        skips+=1


def coasterspage(page):
    try:
        x = requests_session.get(f"https://rcdb.com/r.htm?page={page}&ot=2")
        soup = BeautifulSoup(x.text, 'lxml', parse_only=SoupStrainer(["tr"]))
        div_blocks = soup.find_all('tr')
        div_blocks = div_blocks[4:]
        for selection in div_blocks:
            type = design = status = None
            opened = closed = None
            try:
                cells = selection.find_all('td')
                name = cells[1].text
                url = cells[1].find("a").attrs['href']
                parkurl = RCDB + cells[2].find("a").attrs['href']
                try:
                    type = cleaner(cells[3].text)
                except:
                    pass
                try:
                    design = cleaner(cells[4].text)
                except:
                    pass
                try:
                    status = cleaner(cells[5].text)
                except:
                    pass
                try:
                    opening = cells[6].find_all("time")
                    opened = opening[0].attrs["datetime"].split("-")[0]
                    if len(opening) > 1:
                        closed = opening[1].attrs["datetime"].split("-")[0]
                    else:
                        closed = None
                except:
                    opened = None
                    closed = None
                conn = sqlite3.connect('ParkDatabase.db')
                row = conn.execute("SELECT ParkID FROM Park WHERE RCDBURL = ?", (parkurl,)).fetchone()
                conn.close()
                if row is None:
                    continue
                addCoaster(url, name, opened, closed, design, type, status, row[0])
            except:
                pass
    except IndexError:
        print("No page")


def parkspage(page):
    try:
        x = requests_session.get(f"https://rcdb.com/r.htm?page={page}&ot=3")
        soup = BeautifulSoup(x.text, 'lxml', parse_only=SoupStrainer(["tr"]))
        div_blocks = soup.find_all('tr')
        div_blocks = div_blocks[4:]
        for selection in div_blocks:
            cells = selection.find_all('td')
            name = cells[1].text
            url = RCDB + cells[1].find("a").attrs['href']
            location = cells[2].text
            try:
                status = cleaner(cells[3].text)
            except:
                status = None
            try:
                opening = cells[4].find_all("time")
                opened = opening[0].attrs["datetime"].split("-")[0]
                if len(opening) > 1:
                    closed = opening[1].attrs["datetime"].split("-")[0]
                else:
                    closed = None
            except:
                opened = None
                closed = None
            AddRCDBPark(name, location, status, url, opened, closed)

    except IndexError:
        print("No page")

def searchcoasters(searchfor):
    conn = sqlite3.connect('ParkDatabase.db')

def main():
    global lastparkid
    createDatabaseandTables()
    createAccountTables()
    conn = sqlite3.connect("ParkDatabase.db")
    lastparkid = conn.execute("SELECT MAX(ParkID) FROM Park").fetchone()[0] or 0
    conn.close()
    rebuild_search_index()

    try:
        id = createAccounts("TomMaud", "Password")
    except:
        id = 1
    if id == None:
        id = 1
    conn = sqlite3.connect("ParkDatabase.db")
    conn = sqlite3.connect('ParkDatabase.db')
    CoasterCursor = conn.execute("SELECT * FROM CoasterRidden WHERE AccountID = ? AND Placement IS NOT NULL",
                                 (id,)).fetchall()
    DarkRideCursor = conn.execute("SELECT * FROM DarkRideRidden WHERE AccountID = ? AND Placement IS NOT NULL",
                                  (id,)).fetchall()
    conn.close()
    for i in CoasterCursor:
        removeriddencoaster(id, i[1])
    for i in DarkRideCursor:
        removeriddenDarkride(id, i[1])

    conn = sqlite3.connect("ParkDatabase.db")
    for r in search_parks("Alton"):
        CoasterCursor = conn.execute("SELECT * FROM Coaster WHERE CoasterParkID = ?", (r["ParkID"],)).fetchall()
        DarkCursor = conn.execute("SELECT * FROM DarkRide WHERE DarkRideParkID = ?", (r["ParkID"],)).fetchall()
    conn.close()
    ranking = 1
    for i in CoasterCursor:
        markriddencoaster(id, i[0],ranking)
        ranking += 2
    ranking = 2
    for i in DarkCursor:
        markriddenDarkride(id, i[0],ranking)
        ranking += 2
    rankings = getUsersRankings(id)
    for i in rankings:
        print(i)

    print("\n \n \n \n")

    markriddencoaster(id, '/959.htm',3)
    markriddenDarkride(id, '/6992.htm',1)

    rankings = getUsersRankings(id)
    for i in rankings:
        print(i)
    print("\n \n \n \n")
    removeriddenDarkride(id, "https://darkridedatabase.com/rides/around-the-world-in-80-days/")
    rankings = getUsersRankings(id)
    for i in rankings:
        print(i)

if __name__ == "__main__":
    main()
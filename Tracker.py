import time, requests, random
from bs4 import BeautifulSoup, SoupStrainer
import lxml, threading
import sqlite3
import re
from werkzeug.security import generate_password_hash, check_password_hash

def createAccountTables():
    conn = sqlite3.connect('ParkDatabase.db')
    conn.execute("PRAGMA foreign_keys = ON")


    conn.execute('''
                 CREATE TABLE IF NOT EXISTS Account
                 (
                     AccountID
                     INTEGER
                     PRIMARY
                     KEY,
                     Username
                     TEXT
                     NOT
                     NULL
                     UNIQUE,
                     PasswordHash
                     TEXT
                     NOT
                     NULL,
                     Created
                     TEXT
                     DEFAULT
                     CURRENT_TIMESTAMP
                 )
                 ''')


    conn.execute('''
        CREATE TABLE IF NOT EXISTS CoasterRidden (
            AccountID  INTEGER NOT NULL,
            CoasterURL TEXT NOT NULL,
            Placement      INTEGER,
            PRIMARY KEY (AccountID, CoasterURL),
            FOREIGN KEY (AccountID)  REFERENCES Account(AccountID)  ON DELETE CASCADE,
            FOREIGN KEY (CoasterURL) REFERENCES Coaster(CoasterURL) ON DELETE CASCADE
        )
                 ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS DarkRideRidden (
            AccountID   INTEGER NOT NULL,
            DarkRideURL TEXT NOT NULL,
            Placement      INTEGER,
            PRIMARY KEY (AccountID, DarkRideURL),
            FOREIGN KEY (AccountID)   REFERENCES Account(AccountID)    ON DELETE CASCADE,
            FOREIGN KEY (DarkRideURL) REFERENCES DarkRide(DarkRideURL) ON DELETE CASCADE
        )
                 ''')

    conn.commit()
    conn.close()

def createAccounts(username, password):
    conn = sqlite3.connect('ParkDatabase.db')
    try:
        cur = conn.execute("INSERT INTO Account (Username, PasswordHash) VALUES (?, ?)",
                           (username, generate_password_hash(password)))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def deleteAccount(account_id):
    conn = sqlite3.connect('ParkDatabase.db')
    conn.execute("DELETE FROM Account WHERE AccountID = ?",(account_id,))
    conn.commit()
    conn.close()


def _shift_rankings(conn, account_id, from_placement, delta):
    """Add delta to every placement >= from_placement for this account, across both tables.
    Uses the caller's connection, so it is part of the caller's transaction."""
    for table in ("CoasterRidden", "DarkRideRidden"):
        conn.execute(
            f"UPDATE {table} SET Placement = Placement + ? "
            "WHERE AccountID = ? AND Placement >= ?",
            (delta, account_id, from_placement))


def _mark(account_id, table, column, url, placement):
    conn = sqlite3.connect('ParkDatabase.db')
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        # Make room first, THEN insert, so the new ride isn't shifted along with the others
        if placement is not None:
            _shift_rankings(conn, account_id, placement, +1)
        conn.execute(
            f"INSERT INTO {table} (AccountID, {column}, Placement) VALUES (?, ?, ?)",
            (account_id, url, placement))
        conn.commit()      # shift and insert succeed or fail together
        return True
    except sqlite3.IntegrityError:   # already marked, or unknown account/ride
        conn.rollback()              # undoes the shift too
        return False
    finally:
        conn.close()


def _remove(account_id, table, column, url):
    conn = sqlite3.connect('ParkDatabase.db')
    try:
        deleted = conn.execute(
            f"DELETE FROM {table} WHERE AccountID = ? AND {column} = ? RETURNING Placement",
            (account_id, url)).fetchall()
        if not deleted:              # nothing matched, nothing to close up
            conn.rollback()
            return False
        placement = deleted[0][0]
        if placement is not None:
            # Everything ranked below the removed ride moves up one place
            _shift_rankings(conn, account_id, placement + 1, -1)
        conn.commit()
        return True
    finally:
        conn.close()


def markriddencoaster(account_id, coaster_url, rating=None):
    return _mark(account_id, "CoasterRidden", "CoasterURL", coaster_url, rating)

def removeriddencoaster(account_id, coaster_url):
    return _remove(account_id, "CoasterRidden", "CoasterURL", coaster_url)

def markriddenDarkride(account_id, ride_url, rating=None):
    return _mark(account_id, "DarkRideRidden", "DarkRideURL", ride_url, rating)

def removeriddenDarkride(account_id, ride_url):
    return _remove(account_id, "DarkRideRidden", "DarkRideURL", ride_url)


def updateDarkRiderating(account_id, ride_url, Placement):
    conn = sqlite3.connect('ParkDatabase.db')
    conn.execute("UPDATE DarkRideRidden SET Placement = ? WHERE AccountID = ? AND DarkRideURL = ?",(Placement, account_id, ride_url))
    conn.commit()
    conn.close()

def updateCoasterrating(account_id, ride_url, Placement):
    conn = sqlite3.connect('ParkDatabase.db')
    conn.execute("UPDATE CoasterRidden SET Placement = ? WHERE AccountID = ? AND CoasterURL = ?",(Placement, account_id, ride_url))
    conn.commit()
    conn.close()

def getUsersRankings(account_id):
    conn = sqlite3.connect('ParkDatabase.db')
    coastercursor = conn.execute(
        "SELECT * FROM CoasterRidden WHERE AccountID = ? AND Placement IS NOT NULL ORDER BY Placement",
        (account_id,)).fetchall()
    darkridecursor = conn.execute(
        "SELECT * FROM DarkRideRidden WHERE AccountID = ? AND Placement IS NOT NULL ORDER BY Placement",
        (account_id,)).fetchall()
    rankings = []
    for i in coastercursor:
        coaster = conn.execute("SELECT * FROM Coaster WHERE CoasterURL =?",(i[1],)).fetchone()
        rankings.append({"Name": coaster[1], "Rank": i[2]})
    for i in darkridecursor:
        darkride = conn.execute("SELECT * FROM DarkRide WHERE DarkRideURL =?",(i[1],)).fetchone()
        rankings.append({"Name": darkride[1], "Rank": i[2]})
    rankings.sort(key=lambda x: x["Rank"])
    conn.close()
    return rankings
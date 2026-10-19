import sqlite3

DB = 'ParkDatabase.db'


def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def name_query(column, term):
    words = term.replace('"', '').split()
    if not words:
        return None
    return f'{column} : (' + " ".join(f'"{w}"*' for w in words) + ')'


def rebuild_search_index():
    conn = connect()
    conn.executescript('''
        CREATE VIRTUAL TABLE IF NOT EXISTS ParkSearch
            USING fts5(ParkName, ParkID UNINDEXED);
        CREATE VIRTUAL TABLE IF NOT EXISTS CoasterSearch
            USING fts5(CoasterName, CoasterURL UNINDEXED);
        CREATE VIRTUAL TABLE IF NOT EXISTS DarkRideSearch
            USING fts5(DarkRideName, DarkRideURL UNINDEXED);

        DELETE FROM ParkSearch;
        INSERT INTO ParkSearch (ParkName, ParkID)
            SELECT ParkName, ParkID FROM Park;

        DELETE FROM CoasterSearch;
        INSERT INTO CoasterSearch (CoasterName, CoasterURL)
            SELECT CoasterName, CoasterURL FROM Coaster;

        DELETE FROM DarkRideSearch;
        INSERT INTO DarkRideSearch (DarkRideName, DarkRideURL)
            SELECT DarkRideName, DarkRideURL FROM DarkRide;
    ''')
    conn.commit()
    conn.close()


def search_parks(term, limit=20):
    query = name_query("ParkName", term)
    if query is None:
        return []
    conn = connect()
    rows = conn.execute('''
        SELECT p.ParkID, p.ParkName, p.ParkLocation, p.ParkStatus, p.RCDBURL, p.DRDBURL
        FROM ParkSearch
        JOIN Park p ON p.ParkID = ParkSearch.ParkID
        WHERE ParkSearch MATCH ?
        ORDER BY rank
        LIMIT ?
    ''', (query, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_coasters(term, limit=20):
    query = name_query("CoasterName", term)
    if query is None:
        return []
    conn = connect()
    rows = conn.execute('''
        SELECT c.CoasterURL, c.CoasterName, c.CoasterOpened, c.CoasterClosed,
               c.CoasterDesign, c.CoasterType, c.CoasterStatus,
               p.ParkID, p.ParkName
        FROM CoasterSearch
        JOIN Coaster c ON c.CoasterURL = CoasterSearch.CoasterURL
        JOIN Park p ON p.ParkID = c.CoasterParkID
        WHERE CoasterSearch MATCH ?
        ORDER BY rank
        LIMIT ?
    ''', (query, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_dark_rides(term, limit=20):
    query = name_query("DarkRideName", term)
    if query is None:
        return []
    conn = connect()
    rows = conn.execute('''
        SELECT d.DarkRideURL, d.DarkRideName, d.DarkRideType, d.DarkRideOpened,
               d.DarkRideClosed, d.DarkRideStatus,
               p.ParkID, p.ParkName
        FROM DarkRideSearch
        JOIN DarkRide d ON d.DarkRideURL = DarkRideSearch.DarkRideURL
        JOIN Park p ON p.ParkID = d.DarkRideParkID
        WHERE DarkRideSearch MATCH ?
        ORDER BY rank
        LIMIT ?
    ''', (query, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

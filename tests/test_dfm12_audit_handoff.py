import sqlite3

from dfm12.audit_handoff import finished
from dfm12.io import write_json


def test_both_sources_must_be_prepared_and_terminal(tmp_path):
    write_json(tmp_path / "sources.json", {"sources": [{"component": "acceptability"}, {"component": "correction"}]})
    with sqlite3.connect(tmp_path / "jobs.sqlite") as db:
        db.executescript("""CREATE TABLE sources(component TEXT,complete INTEGER); CREATE TABLE jobs(status TEXT);
                         INSERT INTO sources VALUES ('acceptability',1),('correction',0);""")
    assert not finished(tmp_path)
    with sqlite3.connect(tmp_path / "jobs.sqlite") as db:
        db.execute("UPDATE sources SET complete=1")
        db.execute("INSERT INTO jobs VALUES ('pending')")
    assert not finished(tmp_path)
    with sqlite3.connect(tmp_path / "jobs.sqlite") as db:
        db.execute("UPDATE jobs SET status='parked'")
    assert not finished(tmp_path)
    with sqlite3.connect(tmp_path / "jobs.sqlite") as db:
        db.execute("UPDATE jobs SET status='failed'")
    assert finished(tmp_path)

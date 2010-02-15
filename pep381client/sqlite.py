import sqlite3, os

schema = ["create table if not exists files(project, filename, etag)",
          "create index if not exists files_project on files(project)",
          "create index if not exists files_filename on files(filename)",
          ]

def open(filename):
    conn = sqlite3.connect(filename)
    for stmt in schema:
        conn.execute(stmt)
    conn.commit()
    return conn

def files(cursor, project):
    cursor.execute("select filename from files where project=?", (project,))
    return set(r[0] for r in cursor.fetchall())

def etag(cursor, filename):
    cursor.execute("select etag from files where filename=?", (filename,))
    res = cursor.fetchone()
    if res:
        return res[0]
    else:
        return None

def add_file(cursor, project, filename, etag):
    cursor.execute("insert into files(project, filename, etag) values(?, ?, ?)",
                   (project, filename, etag))

def remove_file(cursor, filename):
    cursor.execute("delete from files where filename=?", (filename,))

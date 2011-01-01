import sqlite3, os

class SqliteStorage(object):

    schema = ["create table if not exists files(project, filename, etag)",
              "create index if not exists files_project on files(project)",
              "create index if not exists files_filename on files(filename)",
              "create table if not exists running(pid)",
              ]

    def __init__(self, filename):
        self.conn = sqlite3.connect(filename)
        cursor = self.conn.cursor()
        for stmt in self.schema:
            cursor.execute(stmt)
        self.commit()

    def commit(self):
        self.conn.commit()

    def files(self, project):
        cursor = self.conn.cursor()
        cursor.execute("select filename from files where project=?", (project,))
        return set(r[0] for r in cursor.fetchall())

    def etag(self, filename):
        cursor = self.conn.cursor()
        cursor.execute("select etag from files where filename=?", (filename,))
        res = cursor.fetchone()
        if res:
            return res[0]
        else:
            return None

    def add_file(self, project, filename, etag):
        cursor = self.conn.cursor()
        cursor.execute("insert into files(project, filename, etag) values(?, ?, ?)",
                       (project, filename, etag))

    def remove_file(self, filename):
        cursor = self.conn.cursor()
        cursor.execute("delete from files where filename=?", (filename,))

    def find_running(self):
        cursor = self.conn.cursor()
        cursor.execute("select pid from running")
        res = cursor.fetchall()
        if not res:
            return None
        return res[0][0]

    def start_running(self, pid):
        cursor = self.conn.cursor()
        cursor.execute("insert into running(pid) values(?)", (pid,))

    def end_running(self):
        cursor = self.conn.cursor()
        cursor.execute("delete from running")

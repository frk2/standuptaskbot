import sqlite3
import datetime
from enum import IntEnum
kDbFile = 'tasks.db'



class Status(IntEnum):
    NEW = 1
    WIP = 2
    DONE = 3
    CANCELLED = 4


class TaskManager:
    tasklist = {}

    def __init__(self):
        self.conn = sqlite3.connect(kDbFile, detect_types=sqlite3.PARSE_DECLTYPES)

    def get_tasklist(self, uid):
        if uid not in self.tasklist:
            self.tasklist[uid] = TaskList(self.conn, uid)

        return self.tasklist[uid]

    def close(self):
        self.conn.close()


class TaskList:
    def __init__(self, conn, uid):
        self.uid = uid
        self.status = None
        self.tasks = {}
        self.conn = conn
        self.load_tasks()

    def load_tasks(self):
        c = self.conn.cursor()
        self.tasks.clear()
        c.execute('SELECT id,task,status,updated from user_tasks where uid=?', (self.uid,))
        for row in c.fetchall():
            self.tasks[row[0]] = (row[1], row[2], row[3])

    def add_task(self, task):
        c = self.conn.cursor()
        c.execute('INSERT into user_tasks (uid,task,status,updated) values (?,?,?,?)',
                  (self.uid, task, Status.NEW, datetime.datetime.now()))
        self.conn.commit()
        self.refresh()

    def refresh(self):
        self.load_tasks()

    def change_status(self, task_id, status):
        c = self.conn.cursor()
        assert status in Status
        c.execute('UPDATE user_tasks set status=? where id=?', (status, task_id))
        self.conn.commit()
        self.refresh()

    def prune(self):
        c = self.conn.cursor()
        c.execute('DELETE from user_tasks where uid=? and (status=? OR status=?)',
                  (self.uid, Status.DONE, Status.CANCELLED))
        self.conn.commit()
        self.refresh()




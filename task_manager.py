import sqlite3
import datetime
from enum import Enum
kDbFile = 'tasks.db'

class Status(Enum):
    NEW = 1
    WIP = 2
    DONE = 3
    CANCELLED = 4

class TaskList:
    def __init__(self, uid):
        self.uid = uid
        self.status = None
        self.tasks = {}
        self.conn = sqlite3.connect(kDbFile, detect_types=sqlite3.PARSE_DECLTYPES)
        self.load_tasks()

    def load_tasks(self):
        c = self.conn.cursor()
        c.execute('SELECT id,task,status,updated from user_tasks where uid=?', (self.uid,))
        for row in c.fetchall():
            self.tasks[row[0]] = (row[1], row[2], row[3])

    def add_task(self, task):
        c = self.conn.cursor()
        c.execute('INSERT into user_tasks (uid,task,status,updated) values (?,?,?,?)',
                  (self.uid, task, 1, datetime.datetime.now()))
        self.conn.commit()



import os
import sqlite3
import time
import threading
import schedule
import json

DB_ADDRESS = 'x-ui.db'
USER_LAST_ID = 0
LIMIT_ACCOUNT_TRAFFIC = 5 * 1024 * 1024 * 1024 # GB


def bytes_to_GB(bytes):
    return bytes / 1024 / 1024 / 1024

def getUsers() -> list[dict]:
    global USER_LAST_ID
    conn = sqlite3.connect(DB_ADDRESS)
    cursor = conn.execute(f"select id,remark,port,settings,protocol from inbounds where id > {USER_LAST_ID}")
    users_list = []
    for c in cursor:
        users_list.append({'name':c[1],'port':c[2],'users':json.loads(c[3]), "protocol": c[4]})
        USER_LAST_ID = c[0]
    conn.close()
    return users_list

def limitAccount(user_port):
    conn = sqlite3.connect(DB_ADDRESS)
    conn.execute(f"update inbounds set total = {LIMIT_ACCOUNT_TRAFFIC} where port={user_port}")
    conn.commit()
    conn.close()
    time.sleep(2)
    os.popen("x-ui restart")
    time.sleep(3)
    
def checkNewUsers():
    # conn = sqlite3.connect(_db_address)
    # cursor = conn.execute(f"select count(*) from inbounds WHERE id > {_user_last_id}")
    # new_counts = cursor.fetchone()[0]
    # conn.close()
    # if new_counts > 0:
    init()


def init():
    users_list = getUsers()
    for user in users_list:
        if not len(user['users']['clients']) > 0:
            continue
        max_conn = user['users']['clients'][0]['email']
        if max_conn == 'unlimited':
            continue
        try:
            max_conn = int(max_conn)
        except ValueError:
            continue
        thread = AccessChecker(user, max_conn)
        thread.start()
        print("starting checker for : " + user['name'])

class AccessChecker(threading.Thread):
    def __init__(self, user, max_conn):
        threading.Thread.__init__(self)
        self.user = user
        self.max_conn = max_conn

    def run(self):
        user_protocol = self.user['protocol']
        if str(user_protocol).lower() not in ['vmess', 'vless', 'shadowsocks', 'trojan']:
            return
        user_remark = self.user['name']
        user_port = self.user['port']
        while True:
            netstate_data =  os.popen("netstat -np 2>/dev/null | grep :"+str(user_port)+" | awk '{if($3!=0) print $5}' | cut -d: -f1 | sort | uniq -c | sort -nr | head").read()
            netstate_data = str(netstate_data)
            connection_count =  len(netstate_data.split("\n")) - 1
            if connection_count > self.max_conn:
                user_remark = user_remark.replace(" ","%20")
                limitAccount(user_port=user_port)
                print(f"inbound with port {user_port} blocked")
            else:
                time.sleep(2)

init()
schedule.every(1).minutes.do(checkNewUsers)
while True:
    schedule.run_pending()
    time.sleep(1)
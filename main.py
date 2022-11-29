import os
import sqlite3
import time
import threading
import schedule
import json

DB_ADDRESS = '/etc/x-ui/x-ui.db'
USER_LAST_ID = 0
LIMIT_ACCOUNT_TRAFFIC = 5 * 1024 * 1024 * 1024 # GB


def getUsers() -> list[dict]:
    global USER_LAST_ID
    conn = sqlite3.connect(DB_ADDRESS)
    cursor = conn.execute(f"select id,remark,port,settings,protocol,total from inbounds where id > {USER_LAST_ID}")
    users_list = []
    for c in cursor:
        users_list.append({"name":c[1],"port":c[2],"users":json.loads(c[3]), "protocol": c[4], "total": c[5]})
        USER_LAST_ID = c[0]
    conn.close()
    return users_list

def limitAccount(user_port, total):
    conn = sqlite3.connect(DB_ADDRESS)
    if total <= LIMIT_ACCOUNT_TRAFFIC:
        conn.execute('update inbounds set enable = 0 where port={user_port}')
        print(f'port {user_port} disabled')
    else:
        conn.execute(f"update inbounds set total = {LIMIT_ACCOUNT_TRAFFIC} where port={user_port}")
        print(f'port {user_port} limited')
    conn.commit()
    conn.close()
    
def checkNewUsers():
    # conn = sqlite3.connect(_db_address)
    # cursor = conn.execute(f"select count(*) from inbounds WHERE id > {_user_last_id}")
    # new_counts = cursor.fetchone()[0]
    # conn.close()
    # if new_counts > 0:
    init()


def init():
    users_list = getUsers()
    approved_num = 0
    for user in users_list:
        if not len(user['users']['clients']) > 0:
            continue
        try:
            max_conn = user['users']['clients'][0]['email']
        except KeyError:
            continue
        if max_conn in ['unlimited', '0']:
            continue
        try:
            max_conn = int(max_conn)
        except ValueError:
            continue
        thread = AccessChecker(user, max_conn)
        thread.start()
        print("starting checker for : " + user['name'])
        approved_num += 1
    if approved_num > 0:
        os.popen("x-ui restart")

class AccessChecker(threading.Thread):
    def __init__(self, user, max_conn):
        threading.Thread.__init__(self)
        self.user = user
        self.max_conn = max_conn

    def stop(self):
        self._stop.set()

    def run(self):
        user_protocol = self.user['protocol']
        if str(user_protocol).lower() not in ['vmess', 'vless', 'shadowsocks', 'trojan']:
            return
        user_remark = self.user['name']
        user_port = self.user['port']
        user_total_traffic = self.user['total']
        while True:
            netstate_data =  os.popen("netstat -np 2> /dev/null | grep :'%s' | awk '{print $5}' | cut -d ':' -f 1 | sort -u | paste -s -d, -" % str(user_port)).read()
            ips_connected = netstate_data.split(",")
            if "\n" == ips_connected[0]:
                del ips_connected[0]
            connection_count = len(ips_connected)
            print(connection_count)
            if connection_count > self.max_conn:
                user_remark = user_remark.replace(" ","%20")
                limitAccount(user_port=user_port, total=user_total_traffic)
                self.stop()
            else:
                time.sleep(2)

init()
print(f'Account Limit Conection Started!')
schedule.every(1).minutes.do(checkNewUsers)
while True:
    schedule.run_pending()
    time.sleep(1)

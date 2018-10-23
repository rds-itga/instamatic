import subprocess as sp
from socket import *
import datetime

from instamatic import config
import logging
import threading
from pathlib import Path

HOST = config.cfg.indexing_server_host
PORT = config.cfg.indexing_server_port
BUFF = 1024

rlock = threading.RLock()


def parse_xds(path):
    """Parse the XDS output file `CORRECT.LP` and print a summary"""
    from instamatic.utils.xds_parser import xds_parser

    fn = Path(path) / "CORRECT.LP"
    
    # rlock prevents messages getting mangled with 
    # simultaneous print statements from different threads
    with rlock:
        if not fn.exists():
            print(f"FAIL: Cannot find file `{fn.name}`, was the indexing successful??")
        else:
            p = xds_parser(fn)
            print()
            p.print_cell()
            print()
            p.print_info()
            print()


def run_xds_indexing(path):
    """Call XDS on the given `path`. Uses WSL (Windows 10 only)."""
    p = sp.Popen("bash -c xds 2>&1 >/dev/null", cwd=path)
    p.wait()

    parse_xds(path)

    now = datetime.datetime.now().strftime("%H:%M:%S.%f")
    print(f"{now} | XDS indexing has finished")


def handle(conn):
    """Handle incoming connection."""
    ret = 0

    while True:
        data = conn.recv(BUFF).decode()
        now = datetime.datetime.now().strftime("%H:%M:%S.%f")

        if not data:
            break
    
        print(f"{now} | {data}")
        if data == "close":
            print(f"{now} | Closing connection")
            break

        elif data == "kill":
            print(f"{now} | Killing server")
            ret = 1
            break

        else:
            conn.send(b"OK")
            run_xds_indexing(data)

    conn.send(b"Connection closed")
    conn.close()
    print("Connection closed")

    return ret


def main():
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    logfile = config.logs_drc / f"instamatic_indexing_server_{date}.log"
    logging.basicConfig(format="%(asctime)s | %(module)s:%(lineno)s | %(levelname)s | %(message)s", 
                        filename=logfile, 
                        level=logging.DEBUG)
    logging.captureWarnings(True)
    log = logging.getLogger(__name__)

    s = socket(AF_INET, SOCK_STREAM)
    s.bind((HOST,PORT))
    s.listen(5)

    log.info(f"Indexing server (XDS) listening on {HOST}:{PORT}")
    print(f"Indexing server (XDS) listening on {HOST}:{PORT}")

    with s:
        while True:
            conn, addr = s.accept()
            log.info('Connected by %s', addr)
            print('Connected by', addr)
            threading.Thread(target=handle, args=(conn,)).start()

    
if __name__ == '__main__':
    main()
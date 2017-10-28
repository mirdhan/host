#!/usr/bin/env python
"""Easy PS4 Exploit Hosting by Al-Azif
   Source: https://github.com/Al-Azif/ps4-exploit-host
"""

# IMPORTS
import ctypes
import os
import SimpleHTTPServer
import socket
import SocketServer
import subprocess
import sys

# GLOBAL VARS
CWD = os.path.dirname(os.path.realpath(__file__)) + os.sep
FAKE_LOC = CWD + 'FakeDns' + os.sep + 'fakedns.py'
DNS_LOC = CWD + 'dns.conf'
EXPLOIT_LOC = CWD + 'exploit' + os.sep


class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    """Create Handler for HTTP Requests (This is so it works for all languages)

       *ALL* HTML requests will directed to "EXPLOIT_LOC/index.html"
       *ALL* JS requests will be directed to like named files in "EXPLOIT_LOC/"
    """
    def do_GET(self):
        try:
            if self.path.endswith('.html'):
                with open(EXPLOIT_LOC + 'index.html') as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(f.read())
            if self.path.endswith('.js'):
                with open(EXPLOIT_LOC + self.path.rsplit(os.sep, 1)[-1]) as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/javascript')
                    self.end_headers()
                    self.wfile.write(f.read())
        except IOError:
            self.send_error(404, 'File Not Found')


def checkroot():
    """Checks if the user is admin/root

       Returns: Boolean
    """
    try:
        root = os.getuid() == 0
    except AttributeError:
        root = ctypes.windll.shell32.IsUserAnAdmin() != 0

    return root


def getlan():
    """Gets the computer's LAN IP

       Returns: String
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        lan = str(s.getsockname()[0])
        s.close()
    except socket.error:
        sys.exit('>> Unable to find LAN IP')

    return lan


def writeconf(lan):
    """Writes the configuration file for FakeDns"""
    try:
        with open(DNS_LOC, 'w') as f:
            f.write('A manuals.playstation.net ' + lan)
        print '>> Your DNS IP is ' + lan
    except IOError:
        sys.exit('>> Unable to write ' + DNS_LOC)


def main():
    """The main logic"""
    if checkroot() is False:
        sys.exit('>> This must be run by root as it requires port 53 & 80')

    writeconf(getlan())

    dns = subprocess.Popen(['python', FAKE_LOC, '-c', DNS_LOC])

    try:
        httpd = SocketServer.TCPServer(('', 80), Handler)
    except socket.error:
        dns.kill()
        sys.exit('>> Port 80 already in use')
    try:
        print '>> Starting HTTP Server...'
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
        dns.kill()
        sys.exit()

if __name__ == '__main__':
    main()

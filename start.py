#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Copyright (c) 2017-2018 Al Azif, https://github.com/Al-Azif/ps4-exploit-host

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

from __future__ import print_function

try:
    import argparse
    import hashlib
    from http.server import BaseHTTPRequestHandler
    from http.server import HTTPServer
    import mimetypes
    import os
    import re
    import socket
    from socketserver import ThreadingMixIn
    import sys
    import threading
    import time
    from urllib.parse import unquote

    import fakedns.fakedns as FAKEDNS
except ImportError:
    if sys.version_info.major < 3:
        print('ERROR: This must be run on Python 3')
        try:
            input('Press [ENTER] to exit')
        finally:
            sys.exit()
    else:
        print('ERROR: Import Error')
        print('Download from the releases page or clone with `--recursive`')
        try:
            input('Press [ENTER] to exit')
        finally:
            sys.exit()

SCRIPT_LOC = os.path.realpath(__file__)
CWD = os.path.dirname(SCRIPT_LOC)
EXPLOIT_LOC = os.path.join(CWD, 'exploits')
PAYLOAD_LOC = os.path.join(CWD, 'payloads')
UPDATE_LOC = os.path.join(CWD, 'updates')
HTML_LOC = os.path.join(CWD, 'html')
STATIC_LOC = os.path.join(CWD, 'static')
SYSTEM_MD5 = '9C85CE3A255719D56F2AA07F4BE22F02'
RECOVERY_MD5 = '6C28DBF66F63B7D3953491CC656F4E2D'
DEBUG = False
AUTOSEND = False


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass


class MyHandler(BaseHTTPRequestHandler):
    try:
        with open(os.path.join(HTML_LOC, 'error.html'), 'rb') as buf:
            error_message_format = buf.read().decode('utf-8')
    except IOError:
        pass
    protocol_version = 'HTTP/1.1'

    def send_response(self, code, message=None):
        """Blanks out default headers"""
        self.log_request(code)
        self.send_response_only(code, message)

    def my_sender(self, mime, content):
        """Here to prevent code duplication"""
        try:
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', len(content))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(content)
        except socket.error:
            print('ERROR: Broken Pipe (Out of Memory?)')

    def updatelist(self):
        region = self.path.split('/')[4]
        path = os.path.join(UPDATE_LOC, 'ps4-updatelist.xml')
        with open(path, 'rb') as buf:
            xml = buf.read()
        xml = xml.replace(b'{{REGION}}', bytes(region, 'utf-8'))
        self.my_sender('application/xml', xml)

    def updatefeature(self):
        path = os.path.join(HTML_LOC, 'ps4-updatefeature.html')
        with open(path, 'rb') as buf:
            data = buf.read()
        self.my_sender('text/html', data)

    def update_pup(self):
        if 'sys' in self.path:
            check_update_pup('SYSTEM', SYSTEM_MD5)
            path = 'PS4UPDATE_SYSTEM.PUP'
        elif 'rec' in self.path:
            check_update_pup('RECOVERY', RECOVERY_MD5)
            path = 'PS4UPDATE_RECOVERY.PUP'
        else:
            path = ''
        path = os.path.join(UPDATE_LOC, path)
        with open(path, 'rb') as buf:
            data = buf.read()
        self.my_sender('text/plain', data)

    def network_test(self, size):
        data = b'\0' * size
        self.my_sender('text/plain', data)

    def exploit_matcher(self):
        with open(os.path.join(HTML_LOC, 'exploits.html'), 'rb') as buf:
            data = buf.read()
        data = self.inject_exploit_html(data)
        self.my_sender('text/html', data)

    def exploit(self):
        path = unquote(self.path.rsplit('/', 1)[-1])
        if not path or path == '/':
            path = 'index.html'
        which = unquote(self.path.rsplit('/')[-2])
        mime = mimetypes.guess_type(path)
        if mime[0]:
            mime = mime[0]
        else:
            mime = 'application/octet-stream'
        with open(os.path.join(EXPLOIT_LOC, which, path), 'rb') as buf:
            data = buf.read()
        if path == 'index.html':
            data = data.replace(b'0.0.0.0', bytes(get_lan(), 'utf-8'))
        self.my_sender(mime, data)

    def static_request(self):
        path = unquote(self.path.rsplit('/', 1)[-1])
        mime = mimetypes.guess_type(path)
        if mime[0]:
            mime = mime[0]
        else:
            mime = 'application/octet-stream'
        with open(os.path.join(STATIC_LOC, path), 'rb') as buf:
            data = buf.read()
        self.my_sender(mime, data)

    def payload_launcher(self):
        payload_menu = True
        for thread in threading.enumerate():
            if thread.name == 'Payload_Brain':
                payload_menu = False

        if payload_menu:
            thread = threading.Thread(name='Payload_Brain',
                                      target=payload_brain,
                                      args=(self.client_address[0],),
                                      daemon=True)
            thread.start()

    def inject_exploit_html(self, html):
        try:
            exploits = os.listdir(EXPLOIT_LOC)
            if 'PUT EXPLOITS HERE' in exploits:
                exploits.remove('PUT EXPLOITS HERE')
            exploits.sort()
            if len(exploits) == 0:
                return html
            elif len(exploits) == 1:
                data = '"{}"'.format(exploits[0])
            else:
                data = '"' + '", "'.join(exploits) + '"'
            data = bytes(data, 'utf-8')
        except IOError:
            pass

        return html.replace(b'{{EXPLOITS}}', data)

    def check_ua(self):
        """Allow 1.76, 4.05, and 4.55 (and there VR spoofs)"""
        allowed = [
            'Mozilla/5.0 (PlayStation 4 1.76) AppleWebKit/536.26 (KHTML, like Gecko)',
            'Mozilla/5.0 (PlayStation 4 4.05) AppleWebKit/537.78 (KHTML, like Gecko)',
            'Mozilla/5.0 (PlayStation 4 5.05) AppleWebKit/537.78 (KHTML, like Gecko)',
            'Mozilla/5.0 (PlayStation 4 4.55) AppleWebKit/601.2 (KHTML, like Gecko)',
            'Mozilla/5.0 (PlayStation 4 5.05) AppleWebKit/601.2 (KHTML, like Gecko)'
        ]

        if self.headers['User-Agent'] in allowed:
            return True
        else:
            return False

    def do_GET(self):
        """Determines how to handle HTTP requests"""
        try:
            if re.match(r'^\/update\/ps4\/list\/[a-z]{2}\/ps4\-updatelist\.xml', self.path):
                self.updatelist()
            elif re.match(r'^\/update\/ps4\/html\/[a-z]{2}\/[a-z]{2}\/ps4\-updatefeature\.html', self.path):
                self.updatefeature()
            elif re.match(r'^\/update\/ps4\/image\/[0-9]{4}_[0-9]{4}\/(sys|rec)\_[a-f0-9]{32}\/PS4UPDATE\.PUP', self.path):
                self.update_pup()
            elif re.match(r'^\/networktest\/get\_2m', self.path):
                self.network_test(2097152)
            elif re.match(r'^\/networktest\/get\_6m', self.path):
                self.network_test(6291456)
            elif re.match(r'^\/$', self.path) or re.match(r'^\/index\.html', self.path) or re.match(r'^\/document\/[a-zA-Z\-]{2,5}\/ps4\/index\.html', self.path) or re.match(r'^\/document\/[a-zA-Z\-]{2,5}\/ps4\/', self.path):
                if self.check_ua():
                    self.exploit_matcher()
                else:
                    self.send_error(400, explain='This PS4 is not on a supported firmware')
                    print('>> Unsupported PS4 attempted to access exploits')
            elif re.match(r'^\/exploits\/.*\/', self.path):
                if self.check_ua():
                    self.exploit()
                else:
                    self.send_error(400, explain='This PS4 is not on a supported firmware')
                    print('>> Unsupported PS4 attempted to access exploits')
            elif re.match(r'^\/static\/', self.path):
                self.static_request()
            else:
                self.send_error(404)
        except IOError:
            self.send_error(404)

        if self.path.rsplit('/', 1)[-1] == 'kernel.js':
            print('>> Exploit sent...')
            try:
                payloads_file = os.path.join(EXPLOIT_LOC, self.path.rsplit('/', 2)[-2], 'nopayloads')
                if os.path.isfile(payloads_file):
                    print('>> Exploit does not support payload, skipping payload menu')
                else:
                    self.payload_launcher()
            except (IOError, PermissionError):
                print('>> ERROR Could not determine if exploit accepts payloads')
                print('>> Payload menu will be loaded anyway...')
                time.sleep(3)
                self.payload_launcher()

    def do_POST(self):
        """Custom POST handler for network test"""
        if re.match(r'^\/networktest\/post\_128', self.path):
            self.send_response(200)
            self.end_headers()


def check_root():
    """Checks if the user is root.

    Windows returns true because there are no priviledged ports
    """
    try:
        root = bool(os.getuid() == 0)
    except AttributeError:
        root = True

    return root


def get_lan():
    """Gets the computer's LAN IP"""
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        soc.connect(('10.255.255.255', 1))
        lan = str(soc.getsockname()[0])
        soc.close()
    except socket.error:
        soc.close()
        closer('ERROR: Unable to find LAN IP')

    return lan


def generate_dns_rules(lan):
    """Creates domain array for FakeDns"""
    rules = []

    try:
        with open(os.path.join(CWD, 'dns.conf'), 'rb') as buf:
            data = buf.read().decode('utf-8')

        for line in data.splitlines():
            line = line.replace('{{SELF}}', lan)
            rules.append(line)
    except (IOError, PermissionError):
        pass

    rules.append('A www.playstation.com ' + lan)
    rules.append('A manuals.playstation.net ' + lan)
    rules.append('A (get|post).net.playstation.net ' + lan)
    rules.append('A (d|f|h)[a-z]{2}01.ps4.update.playstation.net ' + lan)
    rules.append('A gs2.ww.prod.dl.playstation.net ' + lan)
    rules.append('A [a-z0-9\.\-]*.207.net 0.0.0.0')
    rules.append('A [a-z0-9\.\-]*.akadns.net 0.0.0.0')
    rules.append('A [a-z0-9\.\-]*.akamai.net 0.0.0.0')
    rules.append('A [a-z0-9\.\-]*.akamaiedge.net 0.0.0.0')
    rules.append('A [a-z0-9\.\-]*.cddbp.net 0.0.0.0')
    rules.append('A [a-z0-9\.\-]*.ea.com 0.0.0.0')
    rules.append('A [a-z0-9\.\-]*.edgekey.net 0.0.0.0')
    rules.append('A [a-z0-9\.\-]*.edgesuite.net 0.0.0.0')
    rules.append('A [a-z0-9\.\-]*.llnwd.net 0.0.0.0')
    rules.append('A [a-z0-9\.\-]*.playstation.(com|net|org) 0.0.0.0')
    rules.append('A [a-z0-9\.\-]*.ribob01.net 0.0.0.0')
    rules.append('A [a-z0-9\.\-]*.sbdnpd.com 0.0.0.0')
    rules.append('A [a-z0-9\.\-]*.scea.com 0.0.0.0')
    rules.append('A [a-z0-9\.\-]*.sonyentertainmentnetwork.com 0.0.0.0')

    return rules


def check_update_pup(type, md5):
    try:
        update_name = 'PS4UPDATE_{}.PUP'.format(type)
        with open(os.path.join(UPDATE_LOC, update_name), 'rb') as buf:
            data = buf.read()
        check = '>> Checking {}\'s checksum'.format(update_name)
        print(check, end='\r')
        hasher = hashlib.md5()
        hasher.update(data)
        system_hash = hasher.hexdigest().upper()
        if system_hash != md5:
            closer('ERROR: {} is not version 4.55'.format(update_name))
        print('>> {} checksum matches   '.format(update_name))
    except IOError:
        pass


def start_servers(lan, rules, dns_only, http_only):
    """Start DNS and HTTP servers on seperate threads"""
    if not http_only:
        FAKEDNS.main(lan, rules, DEBUG)
        print('>> DNS server thread is running...')

    if not dns_only:
        try:
            server = ThreadedHTTPServer((lan, 80), MyHandler)
            thread = threading.Thread(name='HTTP_Server',
                                      target=server.serve_forever,
                                      args=(),
                                      daemon=True)
            thread.start()
            print('>> HTTP server thread is running...')
        except socket.error:
            closer('ERROR: Could not start server, is another program on tcp:80?')
        except OSError:
            print('ERROR: Could not start server, is another program on tcp:80')
            closer('    ^^This could also be a permission error^^')


def payload_brain(ipaddr):
    """Decides which payloads to send"""
    payloads = []
    try:
        for files in os.listdir(os.path.join(PAYLOAD_LOC)):
            if not files.endswith('PUT PAYLOADS HERE'):
                payloads.append(files)
    except IOError:
        pass

    if AUTOSEND in payloads:
        print('>> Sending {}...'.format(AUTOSEND))
        with open(os.path.join(PAYLOAD_LOC, AUTOSEND), 'rb') as buf:
            content = buf.read()
        content = patch_payload(content)
        send_payload(ipaddr, 9020, content)
        return
    elif len(payloads) <= 0:
        print('>> No payloads in payload folder, skipping payload menu')
    else:
        payloads.insert(0, 'Don\'t send a payload')
        choice = menu('Payload', payloads)
        if choice != 0:
            path = os.path.join(PAYLOAD_LOC, payloads[choice])
            print('>> Sending {}...'.format(payloads[choice]))
            with open(path, 'rb') as buf:
                content = buf.read()
            content = patch_payload(content)
            send_payload(ipaddr, 9020, content)
            # send_another(ipaddr)
            return
        else:
            print('>> No payload sent')


def send_another(ipaddr):
    choice = 0
    while choice != 'Y' and choice != 'N':
        choice = input('Send another payload? (Y/n): ')
        try:
            choice = choice.upper()
        except (ValueError, NameError):
            choice = 0
    if choice == 'Y':
        thread = threading.Thread(name='Payload_Brain',
                                  target=payload_brain,
                                  args=(ipaddr,),
                                  daemon=True)
        thread.start()


def patch_payload(content):
    """Here for later use"""
    return content


def send_payload(hostname, port, content):
    """Netcat implementation"""
    soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    timeout = time.time() + 60
    while True:
        result = soc.connect_ex((hostname, port))
        if result == 0:
            print('>> Connected to PS4')
            timed_out = False
            break
        if time.time() >= timeout:
            print('ERROR: Payload sender timed out')
            timed_out = True
            break
    if not timed_out:
        try:
            soc.sendall(content)
            soc.shutdown(socket.SHUT_WR)
            while True:
                data = soc.recv(1024)
                if not data:
                    break
            print('>> Payload Sent!')
        except socket.error:
            print('ERROR: Broken Pipe')
    soc.close()


def menu(type, input_array):
    """Display a menu

    Type is what ends up in the header of the box
    input array is an array of options
    """
    i = 1
    choice = 0
    print('##########################################################')
    title = '#  {}'.format(type)
    print(format_menu_item(title))
    print('##########################################################')
    for entry in input_array:
        entry = '#  {}. {}'.format(i, entry)
        print(format_menu_item(entry))
        i += 1
    print('##########################################################')
    while choice < 1 or choice >= i:
        input_prompt = 'Choose a {} to send: '.format(type.lower())
        choice = input(input_prompt)
        try:
            choice = int(choice)
        except (ValueError, NameError):
            choice = 0

    return choice - 1


def format_menu_item(entry):
    """Format a menu item to have the box line up"""
    if len(entry) > 58:
        entry = entry[:56]
    while len(entry) < 56:
        entry += ' '
    entry += ' #'
    return entry


def silence_http(self, format, *args):
    """Just blackhole this method to prevent printing"""
    pass


def getch():
    """MIT Licensed: https://github.com/joeyespo/py-getch"""
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def closer(message):
    """Closing method"""
    print(message)
    if message != '\r>> Exiting...                                           ':
        print('Press any key to exit...', end='')
        sys.stdout.flush()
        if os.name == 'nt':
            from msvcrt import getch as w_getch
            w_getch()
        else:
            getch()
        print()
    sys.exit()


def menu_header():
    """Very first thing that prints"""
    print('##########################################################')
    print('#  PS4 Exploit Host                           by Al Azif #')
    print('##########################################################')


def check_args(args):
    """Checks inpout args"""
    global DEBUG
    global AUTOSEND

    if args.debug:
        DEBUG = True
    else:
        MyHandler.log_message = silence_http

    if args.autosend:
        if os.path.isfile(os.path.join(PAYLOAD_LOC, args.autosend)):
            AUTOSEND = args.autosend
        else:
            closer('ERROR: Autosend payload not found')

    if args.dns_only and args.http_only:
        closer('ERROR: No servers selected')

    try:
        if args.interface:
            ip_array = [int(x) for x in args.interface.split('.')]
            if ip_array[0] < 0 or ip_array[0] > 255 or \
               ip_array[1] < 0 or ip_array[1] > 255 or \
               ip_array[2] < 0 or ip_array[2] > 255 or \
               ip_array[3] < 0 or ip_array[3] > 255:
                closer('ERROR: Invalid interface')
    except KeyError:
        closer('ERROR: Invalid interface')


def ip_display(lan, args):
    """Diplay IP and server status"""
    while len(lan) < 15:
        lan += ' '

    if args.http_only:
        server_type = 'HTTP'
    else:
        server_type = 'DNS'
    if args.http_only or args.dns_only:
        running_str = 'Server is running'
    else:
        running_str = 'Servers are running'

    num = int((56 - len(running_str)) / 2)
    running_str = '#' + (' ' * num) + running_str + (' ' * num) + '#'
    if len(running_str) < 58:
        running_str = running_str[:-1] + ' #'

    dns_ip = 'Your {} IP is {}'.format(server_type, lan)
    num = int((56 - len(dns_ip)) / 2)
    dns_ip = '#' + (' ' * num) + dns_ip + (' ' * num) + '#'
    if len(dns_ip) < 58:
        dns_ip = dns_ip[:-1] + ' #'

    print('##########################################################')
    print(running_str)
    print(dns_ip)
    print('##########################################################')


def main():
    """The main logic"""
    menu_header()

    if not check_root():
        closer('ERROR: This must be run by root as it requires port 53 & 80')

    parser = argparse.ArgumentParser(description='PS4 Exploit Host')
    parser.add_argument('--autosend', dest='autosend', action='store',
                        default='', required=False,
                        help='Automatically send payload when exploit loads')
    parser.add_argument('--debug', action='store_true',
                        required=False, help='Print debug statements')
    parser.add_argument('--dns_only', action='store_true',
                        required=False, help='Launch only the DNS server')
    parser.add_argument('--http_only', action='store_true',
                        required=False, help='Launch only the HTTP server')
    parser.add_argument('--interface', dest='interface', action='store',
                        default='', required=False,
                        help='Change the interface the script listens to')
    args = parser.parse_args()

    try:
        check_args(args)

        check_update_pup('SYSTEM', SYSTEM_MD5)
        check_update_pup('RECOVERY', RECOVERY_MD5)

        if not args.interface:
            args.interface = get_lan()

        rules = generate_dns_rules(args.interface)
        start_servers(args.interface, rules, args.dns_only, args.http_only)

        ip_display(args.interface, args)

        while True:
            # Sleep for a day I guess
            time.sleep(24 * 60 * 60)
    except KeyboardInterrupt:
        closer('\r>> Exiting...                                           ')


if __name__ == '__main__':
    main()

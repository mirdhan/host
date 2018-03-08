#!/usr/bin/python3
# -*- coding: utf-8 -*-

from __future__ import print_function

try:
    from distutils.version import StrictVersion
    import hashlib
    from http.server import BaseHTTPRequestHandler
    from http.server import HTTPServer
    import ipaddress
    import json
    import mimetypes
    import os
    import re
    import socket
    from socketserver import ThreadingMixIn
    import sys
    import threading
    import time
    from urllib.parse import unquote
    import urllib.request

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

VERSION = '0.4.1'
API_URL = 'https://api.github.com/repos/Al-Azif/ps4-exploit-host/releases/latest'
SCRIPT_LOC = os.path.realpath(__file__)
CWD = os.path.dirname(SCRIPT_LOC)
EXPLOIT_LOC = os.path.join(CWD, 'exploits')
PAYLOAD_LOC = os.path.join(CWD, 'payloads')
UPDATE_LOC = os.path.join(CWD, 'updates')
HTML_LOC = os.path.join(CWD, 'html')
STATIC_LOC = os.path.join(CWD, 'static')
SETTINGS = None
MENU_OPEN = False


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_resuse_address = True


class MyHandler(BaseHTTPRequestHandler):
    try:
        with open(os.path.join(HTML_LOC, 'error.html'), 'rb') as buf:
            error_message_format = buf.read().decode('utf-8')
    except IOError:
        pass
    protocol_version = 'HTTP/1.1'

    def send_response(self, code, message=None):
        self.log_request(code)
        self.send_response_only(code, message)

    def my_sender(self, mime, content):
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
        fw_version = re.search(r'Download\/1.00 libhttp\/(.+?) \(PlayStation 4\)', self.headers['user-agent'])
        path = os.path.join(UPDATE_LOC, 'ps4-updatelist.xml')

        with open(path, 'rb') as buf:
            xml = buf.read()

        if fw_version:
            try:
                fw_version = float(fw_version.group(1))
                xml = patch_update_xml(xml, region, fw_version)
            except ValueError:
                xml = patch_update_xml(xml, region, 0.00)
        else:
            xml = patch_update_xml(xml, region, 0.00)

        self.my_sender('application/xml', xml)

    def updatefeature(self):
        path = os.path.join(HTML_LOC, 'ps4-updatefeature.html')
        with open(path, 'rb') as buf:
            data = buf.read()
        self.my_sender('text/html', data)

    def update_pup(self):
        if 'sys' in self.path:
            path = 'PS4UPDATE_SYSTEM.PUP'
        elif 'rec' in self.path:
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
        if SETTINGS['Auto_Exploit'] != '':
            refresh_string = '</title>\n<meta http-equiv="refresh" content="0;URL=\'{}\'" />'.format(SETTINGS['Auto_Exploit'])
            data = data.replace(b'</title>', bytes(refresh_string, 'utf-8'))
        self.my_sender('text/html', data)

    def exploit(self):
        path = unquote(self.path.split('/', 2)[-1])
        if path[-1:] == '/':
            path += 'index.html'
        mime = mimetypes.guess_type(self.path.rsplit('/', 1)[-1])
        if mime[0]:
            mime = mime[0]
        else:
            mime = 'application/octet-stream'
        with open(os.path.join(EXPLOIT_LOC, path), 'rb') as buf:
            data = buf.read()
        self.my_sender(mime, data)

    def static_request(self):
        path = unquote(self.path.split('/', 2)[-1])
        if path[-1:] == '/':
            path += 'index.html'
        mime = mimetypes.guess_type(self.path.rsplit('/', 1)[-1])
        if mime[0]:
            mime = mime[0]
        else:
            mime = 'application/octet-stream'
        with open(os.path.join(STATIC_LOC, path), 'rb') as buf:
            data = buf.read()
        self.my_sender(mime, data)

    def inject_exploit_html(self, html):
        try:
            firmwares = os.listdir(EXPLOIT_LOC)
            if 'PUT EXPLOITS HERE' in firmwares:
                firmwares.remove('PUT EXPLOITS HERE')
            for entry in firmwares:
                if os.path.isfile(os.path.join(EXPLOIT_LOC, entry)):
                    firmwares.remove(entry)
            firmwares.sort()
            if len(firmwares) == 0:
                data = json.dumps({'firmwares': ['No Exploits Found']})
                return html.replace(b'{{EXPLOITS}}', bytes(data, 'utf-8'))
            else:
                data = {'firmwares': firmwares}

            for firmware in firmwares:
                exploits = os.listdir(os.path.join(EXPLOIT_LOC, firmware))
                for entry in exploits:
                    if os.path.isfile(os.path.join(EXPLOIT_LOC, firmware, entry)):
                        exploits.remove(entry)
                exploits.sort()
                exploits.append('[Back]')
                data[firmware] = exploits

            data = bytes(json.dumps(data), 'utf-8')
        except IOError:
            data = json.dumps({'firmwares': ['I/O Error on Host']})
            return html.replace(b'{{EXPLOITS}}', bytes(data, 'utf-8'))

        return html.replace(b'{{EXPLOITS}}', data)

    def check_ua(self):
        if self.headers['User-Agent'] in SETTINGS['Valid_UA']:
            return True
        else:
            return False

    def do_GET(self):
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
                if not SETTINGS['UA_Check'] or self.check_ua():
                    self.exploit_matcher()
                else:
                    self.send_error(400, explain='This PS4 is not on a supported firmware')
                    print('>> Unsupported PS4 attempted to access exploits')
            elif re.match(r'^\/exploits\/.*\/', self.path):
                if not SETTINGS['UA_Check'] or self.check_ua():
                    self.exploit()
                else:
                    self.send_error(400, explain='This PS4 is not on a supported firmware')
                    print('>> Unsupported PS4 attempted to access exploits')
            elif re.match(r'^\/success$', self.path):
                self.my_sender('text/plain', b'')
                if not MENU_OPEN:
                    payload_brain(self.client_address[0])
            elif re.match(r'^\/static\/', self.path):
                self.static_request()
            else:
                self.send_error(404)
        except IOError:
            self.send_error(404)

    def do_POST(self):
        if re.match(r'^\/networktest\/post\_128', self.path):
            self.send_response(200)
            self.end_headers()

    def log_message(self, format, *args):
        if SETTINGS['Debug']:
            sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))


def check_root():
    try:
        root = bool(os.getuid() == 0)
    except AttributeError:
        root = True

    return root


def get_lan():
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        soc.connect(('10.255.255.255', 1))
        lan = str(soc.getsockname()[0])
        soc.close()
    except socket.error:
        soc.close()
        closer('ERROR: Unable to find LAN IP')

    return lan


def print_line():
    print('##########################################################')


def center_menu_item(entry):
    num = int((56 - len(entry)) / 2)
    entry = '#' + (' ' * num) + entry + (' ' * num) + '#'
    if len(entry) < 58:
        entry = entry[:-1] + ' #'

    return entry


def payload_menu_item(number, entry):
    entry = '#  {}. {}'.format(number, entry)

    if len(entry) > 58:
        entry = entry[:56]
    while len(entry) < 56:
        entry += ' '
    entry += ' #'

    return entry


def payload_menu(input_array):
    i = 1
    choice = 0
    print_line()
    print('#  Payload                                               #')
    print_line()
    for entry in input_array:
        print(payload_menu_item(i, entry))
        i += 1
    print_line()
    while choice < 1 or choice >= i:
        input_prompt = 'Choose a payload to send: '
        choice = input(input_prompt)
        try:
            choice = int(choice)
        except (ValueError, NameError):
            choice = 0

    return choice - 1


def menu_header():
    print_line()
    print('#  Exploit Host                               by Al Azif #')
    print_line()


def ip_display():
    if SETTINGS['HTTP'] and not SETTINGS['DNS']:
        server_type = 'HTTP'
    else:
        server_type = 'DNS'

    if SETTINGS['HTTP'] and SETTINGS['DNS']:
        server_string = 'Servers are running'
    else:
        server_string = 'Server is running'

    server_string = center_menu_item(server_string)

    ip_string = 'Your {} IP is {}'.format(server_type, SETTINGS['Interface'])
    ip_string = center_menu_item(ip_string)

    print_line()
    print(server_string)
    print(ip_string)
    print_line()


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


def validate_settings():
    """Set to safe defaults if setting is missing or invalid

    This function is huge, gross looking, and will be made pretty in another release
    This is currently here for people who won't read the readme
    Will probably end up throwing a closer error vs correcting in the future
    """

    # Interface ###############################################################
    try:
        try:
            ipaddress.ip_address(SETTINGS['Interface'])
        except ValueError:
            print('ERROR: "Interface" is invalid in settings, reverting to default')
            SETTINGS['Interface'] = get_lan()

        if not SETTINGS['Interface']:
            print('INFO: No interface in settings, set to default')
            SETTINGS['Interface'] = get_lan()
    except KeyError:
        print('ERROR: "Interface" is missing in settings, using default')
        SETTINGS['Interface'] = get_lan()

    # Debug ###################################################################
    try:
        if not isinstance(SETTINGS['Debug'], bool):
            print('ERROR: "Debug" is invalid in settings, reverting to default')
            SETTINGS['Debug'] = False
    except KeyError:
        print('ERROR: "Debug" is missing in settings, using default')
        SETTINGS['Debug'] = False

    # DNS #####################################################################
    try:
        if not isinstance(SETTINGS['DNS'], bool):
            print('ERROR: "DNS" is invalid in settings, reverting to default')
            SETTINGS['DNS'] = True
    except KeyError:
        print('ERROR: "DNS" is missing in settings, using default')
        SETTINGS['DNS'] = True

    # HTTP ####################################################################
    try:
        if not isinstance(SETTINGS['HTTP'], bool):
            print('ERROR: "HTTP" is invalid in settings, reverting to default')
            SETTINGS['HTTP'] = True
    except KeyError:
        print('ERROR: "HTTP" is missing in settings, using default')
        SETTINGS['HTTP'] = True

    # UA Check ################################################################
    try:
        if not isinstance(SETTINGS['UA_Check'], bool):
            print('ERROR: "UA_Check" is invalid in settings, reverting to default')
            SETTINGS['UA_Check'] = True
    except KeyError:
        print('ERROR: "UA_Check" is missing in settings, using default')
        SETTINGS['UA_Check'] = True

    # Auto Exploit ############################################################
    try:
        if not isinstance(SETTINGS['Auto_Exploit'], str) or \
           not os.path.isdir(os.path.join(EXPLOIT_LOC, SETTINGS['Auto_Exploit'])):
            print('ERROR: "Auto_Exploit" is invalid in settings, reverting to default')
            SETTINGS['Auto_Exploit'] = ''
    except KeyError:
        print('ERROR: "Auto_Exploit" is missing in settings, using default')
        SETTINGS['Auto_Exploit'] = ''

    # Auto Payload ############################################################
    try:
        if not isinstance(SETTINGS['Auto_Payload'], str) or \
           not os.path.isfile(os.path.join(PAYLOAD_LOC, SETTINGS['Auto_Payload'])):
            print('ERROR: "Auto_Payload" is invalid in settings, reverting to default')
            SETTINGS['Auto_Payload'] = ''
    except KeyError:
        print('ERROR: "Auto_Payload" is missing in settings, using default')
        SETTINGS['Auto_Payload'] = ''

    # DNS Rules ###############################################################
    try:
        if not isinstance(SETTINGS['DNS_Rules'], dict):
            print('ERROR: "DNS_Rules" is invalid in settings, reverting to default')
            SETTINGS['DNS_Rules'] = ''
        else:
            # Self ############################################################
            if not isinstance(SETTINGS['DNS_Rules']['Self'], list):
                print('ERROR: "DNS_Rules[\'Self\']" is invalid in settings, reverting to default')
                SETTINGS['DNS_Rules']['Self'] = [
                    'www.playstation.com',
                    'manuals.playstation.net',
                    '(get|post).net.playstation.net',
                    '(d|f|h)[a-z]{2}01.ps4.update.playstation.net',
                    'gs2.ww.prod.dl.playstation.net'
                ]
            else:
                if not all(isinstance(x, str) for x in SETTINGS['DNS_Rules']['Self']):
                    print('ERROR: "DNS_Rules[\'Self\']" is malformed in settings, reverting to default')
                    SETTINGS['DNS_Rules']['Self'] = [
                        'www.playstation.com',
                        'manuals.playstation.net',
                        '(get|post).net.playstation.net',
                        '(d|f|h)[a-z]{2}01.ps4.update.playstation.net',
                        'gs2.ww.prod.dl.playstation.net'
                    ]

            # Block ###########################################################
            if not isinstance(SETTINGS['DNS_Rules']['Block'], list):
                print('ERROR: "DNS_Rules[\'Block\']" is invalid in settings, reverting to default')
                SETTINGS['DNS_Rules']['Block'] = [
                    '.*.207.net',
                    '.*.akadns.net',
                    '.*.akamai.net',
                    '.*.akamaiedge.net',
                    '.*.cddbp.net',
                    '.*.ea.com',
                    '.*.edgekey.net',
                    '.*.edgesuite.net',
                    '.*.llnwd.net',
                    '.*.playstation.(com|net|org)',
                    '.*.ribob01.net',
                    '.*.sbdnpd.com',
                    '.*.scea.com',
                    '.*.sonyentertainmentnetwork.com'
                ]
            else:
                if not all(isinstance(x, str) for x in SETTINGS['DNS_Rules']['Block']):
                    print('ERROR: "DNS_Rules[\'Block\']" is malformed in settings, reverting to default')
                    SETTINGS['DNS_Rules']['Block'] = [
                        '.*.207.net',
                        '.*.akadns.net',
                        '.*.akamai.net',
                        '.*.akamaiedge.net',
                        '.*.cddbp.net',
                        '.*.ea.com',
                        '.*.edgekey.net',
                        '.*.edgesuite.net',
                        '.*.llnwd.net',
                        '.*.playstation.(com|net|org)',
                        '.*.ribob01.net',
                        '.*.sbdnpd.com',
                        '.*.scea.com',
                        '.*.sonyentertainmentnetwork.com'
                    ]

            # Pass Through ####################################################
            if not isinstance(SETTINGS['DNS_Rules']['Pass_Through'], list):
                print('ERROR: "DNS_Rules[\'Pass_Through\']" is invalid in settings, reverting to default')
                SETTINGS['DNS_Rules']['Pass_Through'] = ['']
            else:
                if not all(isinstance(x, str) for x in SETTINGS['DNS_Rules']['Pass_Through']):
                    print('ERROR: "DNS_Rules[\'Pass_Through\']" is malformed in settings, reverting to default')
                    SETTINGS['DNS_Rules']['Pass_Through'] = ['']

    except KeyError:
        print('ERROR: "DNS_Rules" or one of it\'s subsettings is missing in settings, using default')
        SETTINGS['DNS_Rules'] = {
            'Self': [
                'www.playstation.com',
                'manuals.playstation.net',
                '(get|post).net.playstation.net',
                '(d|f|h)[a-z]{2}01.ps4.update.playstation.net',
                'gs2.ww.prod.dl.playstation.net'
            ],
            'Block': [
                '.*.207.net',
                '.*.akadns.net',
                '.*.akamai.net',
                '.*.akamaiedge.net',
                '.*.cddbp.net',
                '.*.ea.com',
                '.*.edgekey.net',
                '.*.edgesuite.net',
                '.*.llnwd.net',
                '.*.playstation.(com|net|org)',
                '.*.ribob01.net',
                '.*.sbdnpd.com',
                '.*.scea.com',
                '.*.sonyentertainmentnetwork.com'
            ],
            'Pass_Through': ['']
        }

    # Valid UA ################################################################
    try:
        if not isinstance(SETTINGS['Valid_UA'], list):
            print('ERROR: "Valid_UA" is malformed in settings, using default')
            SETTINGS['Valid_UA'] = [
                "Mozilla/5.0 (PlayStation 4 1.01) AppleWebKit/536.26 (KHTML, like Gecko)",
                "Mozilla/5.0 (PlayStation 4 1.76) AppleWebKit/536.26 (KHTML, like Gecko)",
                "Mozilla/5.0 (PlayStation 4 4.05) AppleWebKit/537.78 (KHTML, like Gecko)",
                "Mozilla/5.0 (PlayStation 4 5.05) AppleWebKit/537.78 (KHTML, like Gecko)",
                "Mozilla/5.0 (PlayStation 4 4.55) AppleWebKit/601.2 (KHTML, like Gecko)",
                "Mozilla/5.0 (PlayStation 4 5.05) AppleWebKit/601.2 (KHTML, like Gecko)",
                "Mozilla/5.0 (PlayStation 4 5.01) AppleWebKit/601.2 (KHTML, like Gecko)",
                "Mozilla/5.0 (PlayStation 4 5.03) AppleWebKit/601.2 (KHTML, like Gecko)",
                "Mozilla/5.0 (PlayStation 4 5.05) AppleWebKit/601.2 (KHTML, like Gecko)",
                "Mozilla/5.0 (PlayStation 4 5.50) AppleWebKit/601.2 (KHTML, like Gecko)"
            ]
        else:
            if not all(isinstance(x, str) for x in SETTINGS['Valid_UA']):
                print('ERROR: "Valid_UA" is malformed in settings, reverting to default')
                SETTINGS['Valid_UA'] = [
                    "Mozilla/5.0 (PlayStation 4 1.01) AppleWebKit/536.26 (KHTML, like Gecko)",
                    "Mozilla/5.0 (PlayStation 4 1.76) AppleWebKit/536.26 (KHTML, like Gecko)",
                    "Mozilla/5.0 (PlayStation 4 4.05) AppleWebKit/537.78 (KHTML, like Gecko)",
                    "Mozilla/5.0 (PlayStation 4 5.05) AppleWebKit/537.78 (KHTML, like Gecko)",
                    "Mozilla/5.0 (PlayStation 4 4.55) AppleWebKit/601.2 (KHTML, like Gecko)",
                    "Mozilla/5.0 (PlayStation 4 5.05) AppleWebKit/601.2 (KHTML, like Gecko)",
                    "Mozilla/5.0 (PlayStation 4 5.01) AppleWebKit/601.2 (KHTML, like Gecko)",
                    "Mozilla/5.0 (PlayStation 4 5.03) AppleWebKit/601.2 (KHTML, like Gecko)",
                    "Mozilla/5.0 (PlayStation 4 5.05) AppleWebKit/601.2 (KHTML, like Gecko)",
                    "Mozilla/5.0 (PlayStation 4 5.50) AppleWebKit/601.2 (KHTML, like Gecko)"
                ]
    except KeyError:
        print('ERROR: "Valid_UA" is missing in settings, using default')
        SETTINGS['Valid_UA'] = [
            "Mozilla/5.0 (PlayStation 4 1.01) AppleWebKit/536.26 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 1.76) AppleWebKit/536.26 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 4.05) AppleWebKit/537.78 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 5.05) AppleWebKit/537.78 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 4.55) AppleWebKit/601.2 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 5.05) AppleWebKit/601.2 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 5.01) AppleWebKit/601.2 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 5.03) AppleWebKit/601.2 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 5.05) AppleWebKit/601.2 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 5.50) AppleWebKit/601.2 (KHTML, like Gecko)"
        ]

    # Update ##################################################################
    try:
        # TODO: Try to correct common errors, set to default on fatal errors
        pass
    except KeyError:
        print('ERROR: "Update" or one of it\'s subsettings is missing in settings, using default')
        SETTINGS['Update'] = {
            "No_Update": 0.00,
            "Max_Update": 0.00,
            "System_MD5": "00000000000000000000000000000000",
            "System_Size": "0",
            "Recovery_MD5": "00000000000000000000000000000000",
            "Recovery_Size": "0",
            "Year": "0000",
            "Month": "00",
            "Day": "00"
        }


def load_settings():
    global SETTINGS

    try:
        with open(os.path.join(CWD, 'settings.json')) as buf:
            SETTINGS = json.loads(buf.read())
    except IOError:
        print('ERROR: Unable to read settings.json')
        print('Expect a bunch of errors as default settings are set')
    except json.decoder.JSONDecodeError:
        print('ERROR: Malformed settings.json')
        print('Expect a bunch of errors as default settings are set')


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


def generate_dns_rules():
    rules = []

    for entry in SETTINGS['DNS_Rules']['Self']:
        rules.append('A {} {}'.format(entry, SETTINGS['Interface']))

    for entry in SETTINGS['DNS_Rules']['Block']:
        rules.append('A {} 0.0.0.0'.format(entry))

    return rules


def start_servers():
    if SETTINGS['DNS']:
        FAKEDNS.main(SETTINGS['Interface'],
                     generate_dns_rules(),
                     SETTINGS['DNS_Rules']['Pass_Through'],
                     SETTINGS['Debug'])
        print('>> DNS server thread is running...')

    if SETTINGS['HTTP']:
        try:
            server = ThreadedHTTPServer((SETTINGS['Interface'], 80), MyHandler)
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


def patch_update_xml(xml, region, version):
    xml = xml.replace(b'{{REGION}}', bytes(region, 'utf-8'))
    if version <= SETTINGS['Update']['No_Update']:
        xml = xml.replace(b'{{YEAR}}', b'0000')
        xml = xml.replace(b'{{MONTH}}', b'00')
        xml = xml.replace(b'{{DAY}}', b'00')
        xml = xml.replace(b'{{SYSTEM_MD5}}', b'00000000000000000000000000000000')
        xml = xml.replace(b'{{SYSTEM_SIZE}}', b'0')
        xml = xml.replace(b'{{RECOVERY_MD5}}', b'00000000000000000000000000000000')
        xml = xml.replace(b'{{RECOVERY_SIZE}}', b'0')
        xml = xml.replace(b'{{VERSION}}', bytes('0.00', 'utf-8'))
        xml = xml.replace(b'{{FULL_VERSION}}', bytes('00.000.000', 'utf-8'))
    else:
        xml = xml.replace(b'{{YEAR}}', bytes(SETTINGS['Update']['Year'], 'utf-8'))
        xml = xml.replace(b'{{MONTH}}', bytes(SETTINGS['Update']['Month'], 'utf-8'))
        xml = xml.replace(b'{{DAY}}', bytes(SETTINGS['Update']['Day'], 'utf-8'))
        xml = xml.replace(b'{{SYSTEM_SIZE}}', bytes(SETTINGS['Update']['System_Size'], 'utf-8'))
        xml = xml.replace(b'{{SYSTEM_MD5}}', bytes(SETTINGS['Update']['System_MD5'].lower(), 'utf-8'))
        xml = xml.replace(b'{{RECOVERY_SIZE}}', bytes(SETTINGS['Update']['Recovery_Size'], 'utf-8'))
        xml = xml.replace(b'{{RECOVERY_MD5}}', bytes(SETTINGS['Update']['Recovery_MD5'].lower(), 'utf-8'))
        if version < SETTINGS['Update']['Max_Update']:
            xml = xml.replace(b'{{VERSION}}', bytes('99.99', 'utf-8'))
            xml = xml.replace(b'{{FULL_VERSION}}', bytes('99.990.000', 'utf-8'))
        elif version >= SETTINGS['Update']['Max_Update']:
            xml = xml.replace(b'{{VERSION}}', bytes(str(version), 'utf-8'))
            xml = xml.replace(b'{{FULL_VERSION}}', bytes('{0:2.3f}.000'.format(version), 'utf-8'))

    return xml


def payload_brain(ipaddr):
    global MENU_OPEN

    payloads = []
    try:
        for files in os.listdir(os.path.join(PAYLOAD_LOC)):
            if not files.endswith('PUT PAYLOADS HERE'):
                payloads.append(files)
    except IOError:
        pass

    if SETTINGS['Auto_Payload'] in payloads:
        print('>> Sending {}...'.format(SETTINGS['Auto_Payload']))
        with open(os.path.join(PAYLOAD_LOC, SETTINGS['Auto_Payload']), 'rb') as buf:
            content = buf.read()
        content = patch_payload(content)
        send_payload(ipaddr, 9020, content)
        return
    elif len(payloads) <= 0:
        print('>> No payloads in payload folder, skipping payload menu')
    else:
        MENU_OPEN = True
        payloads.insert(0, 'Don\'t send a payload')
        choice = payload_menu(payloads)
        if choice != 0:
            path = os.path.join(PAYLOAD_LOC, payloads[choice])
            print('>> Sending {}...'.format(payloads[choice]))
            with open(path, 'rb') as buf:
                content = buf.read()
            content = patch_payload(content)
            send_payload(ipaddr, 9020, content)
            MENU_OPEN = False
            return
        else:
            print('>> No payload sent')


def patch_payload(content):
    return content


def send_payload(hostname, port, content):
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


def version_check():
    try:
        with urllib.request.urlopen(API_URL) as buf:
            response = buf.read()
        response = json.loads(response.decode('utf-8'))

        version_tag = response['tag_name'].replace('v', '')

        if StrictVersion(VERSION) < StrictVersion(version_tag):
            print('WARNING: There is an update availible')
            print('  ^^ Visit https://github.com/Al-Azif/ps4-exploit-host/releases/latest')
    except urllib.error.URLError:
        print('ERROR: Unable to check Github repo to check for updates')
    except ValueError:
        print('WARNING: Unable to check Github repo to check for updates')
        print('  ^^ Visit https://github.com/Al-Azif/ps4-exploit-host/releases/latest')


def main():
    menu_header()

    if not check_root():
        closer('ERROR: This must be run by root as it requires port 53 & 80')

    try:
        version_check()

        load_settings()
        validate_settings()

        check_update_pup('SYSTEM', SETTINGS['Update']['System_MD5'])
        check_update_pup('RECOVERY', SETTINGS['Update']['Recovery_MD5'])

        start_servers()

        ip_display()

        while True:
            time.sleep(24 * 60 * 60)

    except KeyboardInterrupt:
        closer('\r>> Exiting...                                           ')


if __name__ == '__main__':
    main()

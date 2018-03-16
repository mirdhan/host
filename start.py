#!/usr/bin/env python3
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

VERSION = '0.4.2'
API_URL = 'https://api.github.com/repos/Al-Azif/ps4-exploit-host/releases/latest'
SCRIPT_LOC = os.path.realpath(__file__)
CWD = os.path.dirname(SCRIPT_LOC)
EXPLOIT_LOC = os.path.join(CWD, 'exploits')
PAYLOAD_LOC = os.path.join(CWD, 'payloads')
UPDATE_LOC = os.path.join(CWD, 'updates')
THEME_LOC = os.path.join(CWD, 'themes')
SETTINGS = None
MENU_OPEN = False


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_resuse_address = True


class MyHandler(BaseHTTPRequestHandler):
    try:
        with open(os.path.join(THEME_LOC, 'error.html'), 'rb') as buf:
            error_message_format = buf.read().decode('utf-8')
    except (IOError, PermissionError):
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
        path = os.path.join(THEME_LOC, SETTINGS['Theme'], 'ps4-updatefeature.html')
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
        with open(os.path.join(THEME_LOC, SETTINGS['Theme'], 'index.html'), 'rb') as buf:
            data = buf.read()
        data = self.inject_exploit_html(data)
        if SETTINGS['Auto_Exploit'] != '':
            refresh_string = '</title>\n<meta http-equiv="refresh" content="0;URL=/exploits/\'{}\'" />'.format(SETTINGS['Auto_Exploit'])
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
        with open(os.path.join(THEME_LOC, path), 'rb') as buf:
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
        except (IOError, PermissionError):
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
                    if not MENU_OPEN:
                        print('>> Unsupported PS4 attempted to access exploits')
            elif re.match(r'^\/exploits\/.*\/', self.path):
                if not SETTINGS['UA_Check'] or self.check_ua():
                    self.exploit()
                else:
                    self.send_error(400, explain='This PS4 is not on a supported firmware')
                    if not MENU_OPEN:
                        print('>> Unsupported PS4 attempted to access exploits')
            elif re.match(r'^\/success$', self.path):
                self.my_sender('text/plain', b'')
                if not MENU_OPEN:
                    payload_brain(self.client_address[0])
            elif re.match(r'^\/themes\/', self.path):
                self.static_request()
            else:
                self.send_error(404)
        except (IOError, PermissionError):
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


def default_settings():
    global SETTINGS

    SETTINGS = {
        "Interface": get_lan(),
        "Debug": False,
        "DNS": True,
        "HTTP": True,
        "Theme": "default",
        "Auto_Exploit": "",
        "Auto_Payload": "",
        "DNS_Rules": {
            "Self": [
                "www.playstation.com",
                "manuals.playstation.net",
                "(get|post).net.playstation.net",
                "(d|f|h)[a-z]{2}01.ps4.update.playstation.net",
                "gs2.ww.prod.dl.playstation.net"
            ],
            "Block": [
                ".*.207.net",
                ".*.akadns.net",
                ".*.akamai.net",
                ".*.akamaiedge.net",
                ".*.cddbp.net",
                ".*.ea.com",
                ".*.edgekey.net",
                ".*.edgesuite.net",
                ".*.llnwd.net",
                ".*.playstation.(com|net|org)",
                ".*.ribob01.net",
                ".*.sbdnpd.com",
                ".*.scea.com",
                ".*.sonyentertainmentnetwork.com"
            ],
            "Pass_Through": [
                ""
            ]
        },
        "UA_Check": True,
        "Valid_UA": [
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
        ],
        "Update": {
            "No_Update": 1.76,
            "Max_Update": 4.55,
            "System_MD5": "9C85CE3A255719D56F2AA07F4BE22F02",
            "System_Size": "339864576",
            "Recovery_MD5": "6C28DBF66F63B7D3953491CC656F4E2D",
            "Recovery_Size": "918867456",
            "Date": "2017_0411"
        }
    }


def import_settings():
    global SETTINGS

    try:
        with open(os.path.join(CWD, 'settings.json')) as buf:
            imported = json.loads(buf.read())
    except (IOError, PermissionError):
        print('ERROR: Unable to read settings.json, using default')
        return
    except json.decoder.JSONDecodeError:
        print('ERROR: Malformed settings.json, using default')
        return

    if validate_setting(imported, 'Interface', str):
        try:
            ipaddress.ip_address(imported['Interface'])
            SETTINGS['Interface'] = imported['Interface']
        except ValueError:
            print('WARNING: "Interface" in settings is not a valid IP, using default')
    else:
        print('WARNING: "Interface" in settings is invalid, using default')

    if validate_setting(imported, 'Debug', bool):
        SETTINGS['Debug'] = imported['Debug']
    else:
        print('WARNING: "Debug" in settings is invalid, using default')

    if validate_setting(imported, 'DNS', bool):
        SETTINGS['DNS'] = imported['DNS']
    else:
        print('WARNING: "DNS" in settings is invalid, using default')

    if validate_setting(imported, 'HTTP', bool):
        SETTINGS['HTTP'] = imported['HTTP']
    else:
        print('WARNING: "HTTP" in settings is invalid, using default')

    if validate_setting(imported, 'Theme', str) and \
       os.path.isfile(os.path.join(THEME_LOC, imported['Theme'], 'index.html')):
            SETTINGS['Theme'] = imported['Theme']
    elif os.path.isfile(os.path.join(THEME_LOC, 'default', 'index.html')):
        closer('ERROR: "Theme" in settings is invalid, and default is missing')
    else:
        print('WARNING: "Theme" in settings is invalid, using default')

    if (validate_setting(imported, 'Auto_Exploit', str) and
       os.path.isdir(os.path.join(EXPLOIT_LOC, imported['Auto_Exploit']))) or \
       imported['Auto_Exploit'] == '':
            if imported['Auto_Exploit'][:1] == '/' or imported['Auto_Exploit'][:1] == '\\':
                imported['Auto_Exploit'] = imported['Auto_Exploit'][1:]
            SETTINGS['Auto_Exploit'] = imported['Auto_Exploit']
    else:
        print('WARNING: "Auto_Exploit" in settings is invalid, using default')

    if (validate_setting(imported, 'Auto_Payload', str) and
       os.path.isfile(os.path.join(PAYLOAD_LOC, imported['Auto_Payload']))) or \
       imported['Auto_Payload'] == '':
            SETTINGS['Auto_Payload'] = imported['Auto_Payload']
    else:
        print('WARNING: "Auto_Payload" in settings is invalid, using default')

    if validate_setting(imported, 'DNS_Rules', dict):
        if validate_setting(imported['DNS_Rules'], 'Self', list):
            i = 1
            temp_array = []
            for entry in imported['DNS_Rules']['Self']:
                if validate_setting(entry, '', str):
                    temp_array.append(entry)
                else:
                    print('WARNING: Invalid entry in "DNS_Rules[\'Self\'] settings, discarding rule # {}'.format(i))
                i += 1
            SETTINGS['DNS_Rules']['Self'] = imported['DNS_Rules']['Self']
        else:
            print('WARNING: "DNS_Rules[\'Self\']" in settings is invalid, using default')

        if validate_setting(imported['DNS_Rules'], 'Block', list):
            i = 1
            temp_array = []
            for entry in imported['DNS_Rules']['Block']:
                if validate_setting(entry, '', str):
                    temp_array.append(entry)
                else:
                    print('WARNING: Invalid entry in "DNS_Rules[\'Block\'] settings, discarding rule # {}'.format(i))
                i += 1
            SETTINGS['DNS_Rules']['Block'] = imported['DNS_Rules']['Block']
        else:
            print('WARNING: "DNS_Rules[\'Block\']" in settings is invalid, using default')

        if validate_setting(imported['DNS_Rules'], 'Pass_Through', list):
            i = 1
            temp_array = []
            for entry in imported['DNS_Rules']['Pass_Through']:
                if validate_setting(entry, '', str):
                    try:
                        if entry:
                            ipaddress.ip_address(entry)
                            temp_array.append(entry)
                    except ValueError:
                        print('WARNING: Invalid entry in "DNS_Rules[\'Pass_Though\'] settings, discarding rule # {}'.format(i))
                else:
                    print('WARNING: Invalid entry in "DNS_Rules[\'Pass_Though\'] settings, discarding rule # {}'.format(i))
                i += 1
            SETTINGS['DNS_Rules']['Pass_Through'] = imported['DNS_Rules']['Pass_Through']
        else:
            print('WARNING: "DNS_Rules[\'Pass_Through\']" in settings is invalid, using default')
    else:
        print('WARNING: "DNS_Rules" in settings is invalid, using default')

    if validate_setting(imported, 'UA_Check', bool):
        SETTINGS['UA_Check'] = imported['UA_Check']
    else:
        print('WARNING: "UA_Check" in settings is invalid, using default')

    if validate_setting(imported, 'Valid_UA', list):
        i = 1
        temp_array = []
        for entry in imported['Valid_UA']:
            if validate_setting(entry, '', str):
                temp_array.append(entry)
            else:
                print('WARNING: Invalid entry in "Valid_UA" settings, discarding rule # {}'.format(i))
            i += 1
        SETTINGS['Valid_UA'] = temp_array
    else:
        print('WARNING: "Valid_UA" in settings is invalid, using default')

    # Update is either all right or all wrong
    update_test = True
    if validate_setting(imported, 'Update', dict):
        if validate_setting(imported['Update'], 'No_Update', float):
            no_update = '{0:.2f}'.format(imported['Update']['No_Update'])
        else:
            update_test = False

        if validate_setting(imported['Update'], 'Max_Update', float):
            max_update = '{0:.2f}'.format(imported['Update']['Max_Update'])
        else:
            update_test = False

        if update_test and no_update <= max_update:
            pass
        else:
            update_test = False

        if validate_setting(imported['Update'], 'System_MD5', str) and \
           re.match(r'[a-fA-F\d]{32}', imported['Update']['System_MD5']):
            pass
        else:
            update_test = False

        if validate_setting(imported['Update'], 'System_Size', int):
            pass
        else:
            update_test = False

        if validate_setting(imported['Update'], 'Recovery_MD5', str) and \
           re.match(r'[a-fA-F\d]{32}', imported['Update']['Recovery_MD5']):
            pass
        else:
            update_test = False

        if validate_setting(imported['Update'], 'Recovery_Size', int):
            pass
        else:
            update_test = False

        if validate_setting(imported['Update'], 'Date', str):
            pass
        else:
            update_test = False

        if update_test:
            SETTINGS['Update'] = imported['Update']
        else:
            print('WARNING: Subsetting in "Update" setting is invalid, using default')
    else:
        print('WARNING: "Update" in settings is invalid, using default')


def validate_setting(imported, value, type):
    if value:
        check_var = imported[value]
    else:
        check_var = imported
    try:
        if isinstance(check_var, type):
            return True
    except (KeyError, ValueError):
        pass

    return False


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
            closer('ERROR: {} has invalid MD5'.format(update_name))
        print('>> {} checksum matches   '.format(update_name))
    except (IOError, PermissionError):
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
        except UnicodeDecodeError:
            print('ERROR: Python failed to get a FQDN (This is a Python Bug)')
            closer('    ^^Change your computers name to be [a-zA-Z0-9]^^')


def patch_update_xml(xml, region, version):
    xml = xml.replace(b'{{REGION}}', bytes(region, 'utf-8'))
    if version <= SETTINGS['Update']['No_Update']:
        xml = xml.replace(b'{{DATE}}', b'0000_0000')
        xml = xml.replace(b'{{SYSTEM_MD5}}', b'00000000000000000000000000000000')
        xml = xml.replace(b'{{SYSTEM_SIZE}}', b'0')
        xml = xml.replace(b'{{RECOVERY_MD5}}', b'00000000000000000000000000000000')
        xml = xml.replace(b'{{RECOVERY_SIZE}}', b'0')
        xml = xml.replace(b'{{VERSION}}', bytes('0.00', 'utf-8'))
        xml = xml.replace(b'{{FULL_VERSION}}', bytes('00.000.000', 'utf-8'))
    else:
        xml = xml.replace(b'{{DATE}}', bytes(SETTINGS['Update']['Date'], 'utf-8'))
        xml = xml.replace(b'{{SYSTEM_SIZE}}', bytes(str(SETTINGS['Update']['System_Size']), 'utf-8'))
        xml = xml.replace(b'{{SYSTEM_MD5}}', bytes(SETTINGS['Update']['System_MD5'].lower(), 'utf-8'))
        xml = xml.replace(b'{{RECOVERY_SIZE}}', bytes(str(SETTINGS['Update']['Recovery_Size']), 'utf-8'))
        xml = xml.replace(b'{{RECOVERY_MD5}}', bytes(SETTINGS['Update']['Recovery_MD5'].lower(), 'utf-8'))
        if version <= SETTINGS['Update']['Max_Update']:
            xml = xml.replace(b'{{VERSION}}', bytes(str(version), 'utf-8'))
            xml = xml.replace(b'{{FULL_VERSION}}', bytes('{0:2.3f}.000'.format(version), 'utf-8'))
        elif version > SETTINGS['Update']['Max_Update']:
            xml = xml.replace(b'{{VERSION}}', bytes('99.99', 'utf-8'))
            xml = xml.replace(b'{{FULL_VERSION}}', bytes('99.990.000', 'utf-8'))

    return xml


def payload_brain(ipaddr):
    global MENU_OPEN

    payloads = []
    try:
        for files in os.listdir(os.path.join(PAYLOAD_LOC)):
            if not files.endswith('PUT PAYLOADS HERE'):
                payloads.append(files)
    except (IOError, PermissionError):
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

        default_settings()
        import_settings()

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

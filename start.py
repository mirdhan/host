#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function

try:
    import argparse
    from cgi import parse_header
    from cgi import parse_multipart
    from cgi import parse_qs
    import copy
    from distutils.version import StrictVersion
    from http.server import BaseHTTPRequestHandler
    from http.server import HTTPServer
    import hashlib
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
    from urllib.parse import quote
    from urllib.parse import unquote
    import urllib.request
    import zlib

    import fakedns.fakedns as FAKEDNS
except ImportError:
    import sys
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

VERSION = '0.4.6'
API_URL = 'https://api.github.com/repos/Al-Azif/ps4-exploit-host/releases/latest'
SCRIPT_LOC = os.path.realpath(__file__)
CWD = os.path.dirname(SCRIPT_LOC)
EXPLOIT_LOC = os.path.join(CWD, 'exploits')
PAYLOAD_LOC = os.path.join(CWD, 'payloads')
UPDATE_LOC = os.path.join(CWD, 'updates')
THEME_LOC = os.path.join(CWD, 'themes')
DEBUG_LOC = os.path.join(CWD, 'debug')
SETTINGS = None
MENU_OPEN = False
DEBUG_VAR = {}


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_resuse_address = True
    request_queue_size = 16


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
        if SETTINGS['Compression_Level'] > 0:
            gzip = zlib.compressobj(SETTINGS['Compression_Level'], zlib.DEFLATED, zlib.MAX_WBITS | 16)
            content = gzip.compress(content) + gzip.flush()
        try:
            self.send_response(200)
            self.send_header('Content-Type', mime)
            if SETTINGS['Compression_Level'] > 0:
                self.send_header('Content-Encoding', 'gzip')
            self.send_header('Content-Length', len(content))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(content)
        except socket.error:
            print('ERROR: Broken Pipe')

    def updatelist(self):
        region = self.path.split('/')[4]
        ps4_version = re.search(r'^Download\/1.00 libhttp\/(.+?) \(PlayStation 4\)$', self.headers['user-agent'])
        vita_version = re.search(r'^libhttp\/(.+?) \(PS Vita\)$', self.headers['user-agent'])
        ps4_net_test = re.match(r'^HttpTestWrapperUser libhttp\/.* \(PlayStation 4\)$', self.headers['user-agent'])
        vita_net_test = re.match(r'SOMETHING THAT WONT MATCH', self.headers['user-agent'])

        try:
            if not ps4_version and not vita_version and not ps4_net_test and not vita_net_test:
                self.send_error(404)
                return
            elif ps4_version:
                fw_version = float(ps4_version.group(1))
            elif vita_version:
                fw_version = float(vita_version.group(1))
        except ValueError:
            self.send_error(404)
            return

        if (ps4_version and fw_version > SETTINGS['Update']['PS4_No_Update']) or ps4_net_test:
            path = os.path.join(UPDATE_LOC, 'ps4-updatelist.xml')
        elif (vita_version and fw_version > SETTINGS['Update']['Vita_No_Update']) or vita_net_test:
            path = os.path.join(UPDATE_LOC, 'psp2-updatelist.xml')
        else:
            self.send_error(404)
            return

        with open(path, 'rb') as buf:
            xml = buf.read()

        xml = xml.replace(b'{{REGION}}', bytes(region, 'utf-8'))

        self.my_sender('application/xml', xml)

    def updatefeature(self):
        path = os.path.join(THEME_LOC, SETTINGS['Theme'], 'ps4-updatefeature.html')
        with open(path, 'rb') as buf:
            data = buf.read()
        self.my_sender('text/html', data)

    def update_pup(self):
        if re.match(r'^\/update\/ps4\/image\/[0-9]{4}_[0-9]{4}\/sys\_[a-fA-F0-9]{32}\/PS4UPDATE\.PUP', self.path):
            path = 'PS4UPDATE_SYSTEM.PUP'
        elif re.match(r'^\/update\/ps4\/image\/[0-9]{4}_[0-9]{4}\/rec\_[a-fA-F0-9]{32}\/PS4UPDATE\.PUP', self.path):
            path = 'PS4UPDATE_RECOVERY.PUP'
        elif re.match(r'^\/update\/psp2\/image\/[0-9]{4}_[0-9]{4}\/rel\_[a-fA-F0-9]{32}\/PSP2UPDAT\.PUP', self.path):
            path = 'PSP2UPDAT.PUP'
        else:
            self.send_error(404)
            return
        path = os.path.join(UPDATE_LOC, path)
        with open(path, 'rb') as buf:
            data = buf.read()
        self.my_sender('text/plain', data)

    def network_test(self, size):
        data = b'\0' * size
        self.my_sender('text/plain', data)

    def api_categories(self):
        try:
            categories = os.listdir(EXPLOIT_LOC)
            for entry in categories:
                if os.path.isfile(os.path.join(EXPLOIT_LOC, entry)) or len(os.listdir(os.path.join(EXPLOIT_LOC, entry))) == 0:
                    categories.remove(entry)
            categories.sort()
            if len(categories) == 0:
                data = b'["No Categories Found"]'
            else:
                data = bytes(json.dumps(categories), 'utf-8')
        except (IOError, PermissionError):
            data = b'["I/O Error on Host"]'

        if data != b'["No Categories Found"]' and data != b'["I/O Error on Host"]':
            pass # TODO: Combine all meta.json files for categories

        self.my_sender('application/json', data)

    def api_entries(self, path):
        path = unquote(path)
        try:
            category = os.listdir(os.path.join(EXPLOIT_LOC, path))
            for entry in category:
                if os.path.isfile(os.path.join(EXPLOIT_LOC, path, entry)):
                    category.remove(entry)
            category.sort()
            if len(category) == 0:
                data = b'["No Entries Found"]'
            else:
                data = bytes(json.dumps(category), 'utf-8')
        except (IOError, PermissionError):
            data = b'["I/O Error on Host"]'

        if data != b'["No Entries Found"]' and data != b'["I/O Error on Host"]':
            pass # TODO: Combine all meta.json files for entries

        self.my_sender('application/json', data)

    def api_view_settings(self):
        safe_settings = copy.deepcopy(SETTINGS)
        try:
            del safe_settings['Root_Check']
            del safe_settings['DNS']
            del safe_settings['HTTP']
            del safe_settings['DNS_Interface_IP']
            del safe_settings['DNS_Port']
            del safe_settings['HTTP_Interface_IP']
            del safe_settings['HTTP_Port']
        except KeyError:
            pass
        self.my_sender('application/json', bytes(json.dumps(safe_settings), 'utf-8'))

    def api_edit_settings(self, data):
        # TODO
        pass

    def menu(self):
        with open(os.path.join(THEME_LOC, SETTINGS['Theme'], 'index.html'), 'rb') as buf:
            data = buf.read()
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

    def news(self):
        with open(os.path.join(CWD, 'news.json'), 'rb') as buf:
            data = buf.read()
        self.my_sender('application/json', data)

    def generate_cacher(self):
        if re.match(r'^\/cache\/category\/.*\/index.html$', self.path):
            category = unquote(self.path.split('/')[3])
            cache_this = 'category/' + category
        elif re.match(r'^\/cache\/entry\/.*\/.*\/index.html$', self.path):
            category = unquote(self.path.split('/')[3])
            entry = unquote(self.path.split('/')[4])
            cache_this = 'entry/' + category + '/' + entry
        elif re.match(r'^\/cache\/redirect\/[a-zA-Z\-]{2,5}\/index.html$', self.path):
            result = re.search(r'^\/cache\/redirect\/([a-zA-Z\-]{2,5})\/index.html$', self.path)
            country = result.group(1)
            cache_this = 'redirect'
        elif re.match(r'\/cache\/theme\/index.html$', self.path):
            cache_this = 'theme'
        elif re.match(r'^\/cache\/all\/index.html$', self.path):
            cache_this = 'all'
        else:
            self.send_error(404)
            return

        if cache_this == 'redirect':
            html = b'<!DOCTYPE html><html manifest="/cache/redirect/{{COUNTRY}}/offline.manifest"><head><meta charset=utf-8><title>Cacher</title><script>window.applicationCache.ondownloading=function(){parent.cacheInterface("ondownloading-redirect");};window.applicationCache.onprogress=function(n){parent.cacheProgress(Math.round(n.loaded/n.total*100));};window.applicationCache.oncached=function(){parent.cacheInterface("oncached-redirect");};window.applicationCache.onupdateready=function(){parent.cacheInterface("onupdateready-redirect");};window.applicationCache.onnoupdate=function(){parent.cacheInterface("onnoupdate-redirect");};window.applicationCache.onerror=function(){parent.cacheInterface("onerror-redirect");};window.applicationCache.onobsolete=function(){parent.cacheInterface("onobsolete-redirect");};</script></head></html>'
            html = html.replace(b'{{COUNTRY}}', bytes(country, 'utf-8'))
        elif cache_this == 'theme':
            html = b'<!DOCTYPE html><html manifest="/theme.manifest"><head><meta charset=utf-8><title>Cacher</title><script>window.applicationCache.ondownloading=function(){parent.cacheInterface("ondownloading-theme");};window.applicationCache.onprogress=function(n){parent.cacheProgress(Math.round(n.loaded/n.total*100));};window.applicationCache.oncached=function(){parent.cacheInterface("oncached-theme");};window.applicationCache.onupdateready=function(){parent.cacheInterface("onupdateready-theme");};window.applicationCache.onnoupdate=function(){parent.cacheInterface("onnoupdate-theme");};window.applicationCache.onerror=function(){parent.cacheInterface("onerror-theme");};window.applicationCache.onobsolete=function(){parent.cacheInterface("onobsolete-theme");};</script></head></html>'
        else:
            html = b'<!DOCTYPE html><html manifest="/cache/{{CACHE_THIS}}/offline.manifest"><head><meta charset=utf-8><title>Cacher</title><script>window.applicationCache.ondownloading=function(){parent.cacheInterface("ondownloading");};window.applicationCache.onprogress=function(n){parent.cacheProgress(Math.round(n.loaded/n.total*100));};window.applicationCache.oncached=function(){parent.cacheInterface("oncached");};window.applicationCache.onupdateready=function(){parent.cacheInterface("onupdateready");};window.applicationCache.onnoupdate=function(){parent.cacheInterface("onnoupdate");};window.applicationCache.onerror=function(){parent.cacheInterface("onerror");};window.applicationCache.onobsolete=function(){parent.cacheInterface("onobsolete");};</script></head></html>'
            html = html.replace(b'{{CACHE_THIS}}', bytes(cache_this, 'utf-8'))

        self.my_sender('text/html', html)

    def generate_manifest(self):
        cache_all = False

        if re.match(r'^\/cache\/category\/.*\/offline.manifest$', self.path):
            req_category = unquote(self.path.split('/')[3])
        elif re.match(r'^\/cache\/entry\/.*\/.*\/offline.manifest$', self.path):
            req_category = unquote(self.path.split('/')[3])
            req_entry = unquote(self.path.split('/')[4])
        elif re.match(r'\/cache\/redirect\/[a-zA-Z\-]{2,5}\/offline.manifest$', self.path):
            self.theme_manifest()
            return
        elif re.match(r'\/cache\/all\/offline.manifest$', self.path):
            cache_all = True
        else:
            self.send_error(404)
            return

        hasher = hashlib.md5()

        manifest = 'CACHE MANIFEST\n\n'
        manifest +='CACHE:\n'

        for path, subdirs, files in os.walk(EXPLOIT_LOC):
            for filename in files:
                split_path = (path.replace(CWD, '').replace('\\', '/')).split('/')
                if len(split_path) > 2:
                    if cache_all or split_path[2] == req_category:
                        try:
                            if cache_all or split_path[3] == req_entry:
                                with open(os.path.join(path, filename), 'rb') as buf:
                                    data = buf.read()
                                hasher.update(data)
                                manifest += quote(os.path.join(path, filename).replace(CWD, '').replace('\\', '/'), safe='+?&:/()') + '\n'
                        except (ValueError, NameError):
                            with open(os.path.join(path, filename), 'rb') as buf:
                                data = buf.read()
                            hasher.update(data)
                            if filename != 'PUT EXPLOITS HERE':
                                manifest += quote(os.path.join(path, filename).replace(CWD, '').replace('\\', '/'), safe='+?&:/()') + '\n'
                        except IndexError:
                            pass

        manifest += '\nNETWORK:\n'
        manifest += '*\n'

        manifest += '\n# Hash: {}'.format(hasher.hexdigest().upper())

        self.my_sender('text/cache-manifest', bytes(manifest, 'utf-8'))

    def theme_manifest(self):
        hasher = hashlib.md5()

        manifest = 'CACHE MANIFEST\n\n'
        manifest +='CACHE:\n'

        manifest += '/\n'
        manifest += 'index.html\n'
        manifest += '/index.html\n'
        manifest += '/blank.html\n'

        if not re.match(r'^\/cache\/redirect\/[a-zA-Z\-]{2,5}\/offline\.manifest$', self.path):
            manifest += '/api/categories\n'

            categories = os.listdir(EXPLOIT_LOC)
            if 'PUT EXPLOITS HERE' in categories:
                categories.remove('PUT EXPLOITS HERE')
            for entry in categories:
                if os.path.isfile(os.path.join(EXPLOIT_LOC, entry)):
                    categories.remove(entry)
            categories.sort()

            for entry in categories:
                manifest += quote('/api/entries/{}'.format(entry), safe='+?&:/()') + '\n'

            for path, subdirs, files in os.walk(EXPLOIT_LOC):
                for directory in subdirs:
                    hasher.update(bytes(directory, 'utf-8'))
                for filename in files:
                    if filename == 'meta.json':
                        with open(os.path.join(path, filename), 'rb') as buf:
                            data = buf.read()
                        hasher.update(data)
                        manifest += quote(os.path.join(path, filename).replace(CWD, '').replace('\\', '/'), safe='+?&:/()') + '\n'
        else:
            result = re.search(r'^\/cache\/redirect\/([a-zA-Z\-]{2,5})\/offline\.manifest$', self.path)
            manifest += '/document/{}/ps4/index.html\n'.format(result.group(1))

        for path, subdirs, files in os.walk(os.path.join(THEME_LOC, SETTINGS['Theme'])):
            for filename in files:
                with open(os.path.join(path, filename), 'rb') as buf:
                    data = buf.read()
                hasher.update(data)
                manifest += quote(os.path.join(path, filename).replace(CWD, '').replace('\\', '/'), safe='+?&:/()') + '\n'

        manifest += '\nNETWORK:\n'
        manifest += '*\n'

        manifest += '\n# Hash: {}'.format(hasher.hexdigest().upper())

        self.my_sender('text/cache-manifest', bytes(manifest, 'utf-8'))

    def check_ua(self):
        for ua in SETTINGS['Valid_UA']:
            ua_test = re.compile(ua)
            if ua_test.match(self.headers['User-Agent']):
                return True
        return False

    def do_GET(self):
        self.path = self.path.split('?')[0]
        try:
            if re.match(r'^\/update\/(ps4|psp2)\/list\/[a-z]{2}\/(ps4|psp2)\-updatelist\.xml', self.path):
                self.updatelist()
                return
            elif re.match(r'^\/update\/ps4\/html\/[a-z]{2}\/[a-z]{2}\/ps4\-updatefeature\.html', self.path):
                self.updatefeature()
                return
            elif re.match(r'^\/update\/(ps4|psp2)\/image\/[0-9]{4}_[0-9]{4}\/(sys|rec|rel)\_[a-fA-F0-9]{32}\/(PS4UPDATE\.PUP|PSP2UPDAT\.PUP)', self.path):
                self.update_pup()
                return
            elif re.match(r'^\/networktest\/get\_2m', self.path):
                self.network_test(2097152)
                return
            elif re.match(r'^\/networktest\/get\_6m', self.path):
                self.network_test(6291456)
                return
            elif re.match(r'^\/api\/', self.path):
                if re.match(r'^\/api\/categories$', self.path):
                    self.api_categories()
                    return
                elif re.match(r'^\/api\/entries\/.*', self.path):
                    category = re.search(r'^\/api\/entries\/(.*)', self.path)
                    if category:
                        self.api_entries(category.group(1))
                        return
                    else:
                        self.send_error(404)
                        return
                elif re.match(r'^\/api\/settings\/view$', self.path) and not SETTINGS['Public']:
                    self.api_view_settings()
                    return
                else:
                    self.send_error(404)
                    return
            elif re.match(r'^\/$', self.path) or re.match(r'^\/index\.html$', self.path) or re.match(r'^\/document\/[a-zA-Z\-]{2,5}\/(ps4|psvita)\/index.html$', self.path):
                if not SETTINGS['UA_Check'] or self.check_ua():
                    self.menu()
                    return
                else:
                    self.send_error(400, explain='This device is not supported')
                    if not MENU_OPEN:
                        print('>> Unsupported device attempted to access exploits')
                    return
            elif re.search(r'\/theme\.manifest$', self.path):
                self.theme_manifest()
                return
            elif re.match(r'^\/cache\/.*\/index.html$', self.path):
                self.generate_cacher()
                return
            elif re.match(r'^\/cache\/.*\/offline.manifest$', self.path):
                self.generate_manifest()
                return
            elif re.match(r'^\/exploits\/.*\/', self.path):
                self.exploit()
                return
            elif re.match(r'^\/success$', self.path):
                self.my_sender('text/plain', b'')
                if not MENU_OPEN:
                    payload_brain(self.client_address[0])
                return
            elif re.match(r'^\/success\/[0-9]{1,5}\/[0-9]{1,3}\/.*$', self.path) and not SETTINGS['Public']:
                self.my_sender('text/plain', b'')
                result = re.search(r'^\/success\/([0-9]{1,5})\/([0-9]{1,3})\/(.*)$', self.path)
                if int(result.group(1)) < 1 or int(result.group(1)) > 65535:
                    print('>> Success request port number is out of range')
                elif int(result.group(2)) < 0 or int(result.group(2)) > 999:
                    print('>> Success request timeout is out of range')
                else:
                    try:
                        with open(os.path.join(PAYLOAD_LOC, result.group(3)), 'rb') as buf:
                            print('>> Sending {}...'.format(result.group(3)))
                            send_payload(self.address_string(), int(result.group(1)), int(result.group(2)), buf.read())
                    except (IOError, PermissionError):
                        print('>> Success request payload ({}) not found'.format(result.group(2)))
                return
            elif re.match(r'^\/themes\/', self.path):
                self.static_request()
                return
            elif re.match(r'\/news$', self.path):
                self.news()
                return
            elif re.match(r'\/blank.html$', self.path):
                self.my_sender('text/html', b'<html><head><meta charset="utf-8"><title>Deus Machina</title></head><body>ZmzJCgLnJ43j2FK4NUR/EmFc7hJRN7Ub4adlqCRLfsXoswDsjyvn5vGwLj2FZdOlVLNmi/l0mjiuHgCYSZqPSndVhg6U8ODSl1+/aDxQLZE=</body></html>')
                return
            elif re.match(r'^\/debug\/var\/[a-zA-Z0-9\-\_\.]*$', self.path):
                try:
                    result = re.search(r'^\/debug\/var\/([a-zA-Z0-9\-\_\.]*)$', self.path)
                    self.my_sender('text/plain', DEBUG_VAR[result.group(1)])
                except KeyError:
                    self.send_error(404)
                return
            else:
                self.send_error(404)
                return
        except (IOError, PermissionError):
            self.send_error(404)
            return

    def parse_POST(self):
        ctype, pdict = parse_header(self.headers['content-type'])
        if ctype == 'multipart/form-data':
            postvars = parse_multipart(self.rfile, pdict)
        elif ctype == 'application/x-www-form-urlencoded':
            length = int(self.headers['content-length'])
            postvars = parse_qs(self.rfile.read(length), keep_blank_values=1)
        else:
            postvars = {}
        return postvars

    def do_POST(self):
        try:
            post_data = self.parse_POST()

            if re.match(r'^\/networktest\/post\_128', self.path):
                self.my_sender('text/plain', b'')
                return
            elif re.match(r'^\/api\/settings\/edit$', self.path) and not SETTINGS['Public']:
                self.api_edit_settings(post_data)
                self.my_sender('text/plain', b'')
                return
            elif re.match(r'^\/debug\/jserrorlog$', self.path):
                message =  '--------------------------------------------------------------------------------\n'
                message += '    Message:    ' + post_data[b'message'][0].decode('utf-8') + '\n'
                message += '    Line:       ' + post_data[b'line'][0].decode('utf-8') + '\n'
                message += '    Column:     ' + post_data[b'column'][0].decode('utf-8') + '\n'
                message += '    URL:        ' + post_data[b'url'][0].decode('utf-8') + '\n'
                message += '    User-Agent: ' + post_data[b'useragent'][0].decode('utf-8') + '\n'
                message += '    Stack:      ' + post_data[b'stack'][0].decode('utf-8') + '\n'
                with open(os.path.join(DEBUG_LOC, 'js-error.log'), 'a+') as buf:
                    buf.write(message)
                self.my_sender('text/plain', b'')
                return
            elif re.match(r'^\/debug\/filedump$', self.path) and not SETTINGS['Public']:
                if post_data[b'filename'][0].decode('utf-8') != 'js-error.log' and \
                   post_data[b'filename'][0].decode('utf-8') != 'httpd.log':
                    with open(os.path.join(DEBUG_LOC, post_data[b'filename'][0].decode('utf-8')), 'rb+') as buf:
                        buf.seek(int(post_data[b'offset'][0]), 0)
                        buf.write(post_data[b'data'][0])
                    self.my_sender('text/plain', b'')
                    return
                else:
                    self.send_error(404)
                    return
            elif re.match(r'^\/debug\/filedelete$', self.path) and not SETTINGS['Public']:
                if post_data[b'filename'][0].decode('utf-8') != 'js-error.log' and \
                   post_data[b'filename'][0].decode('utf-8') != 'httpd.log':
                    if os.path.isfile(os.path.join(DEBUG_LOC, post_data[b'filename'][0].decode('utf-8'))):
                        os.remove(os.path.join(DEBUG_LOC, post_data[b'filename'][0].decode('utf-8')))
                    self.my_sender('text/plain', b'')
                    return
                else:
                    self.send_error(404)
                    return
            elif re.match(r'^\/debug\/var\/[a-zA-Z0-9\-\_\.]*$', self.path) and not SETTINGS['Public']:
                result = re.search(r'^\/debug\/var\/([a-zA-Z0-9\-\_\.]*)$', self.path)
                DEBUG_VAR[result.group(1)] = self.rfile.read(int(self.headers['Content-Length']))
                self.my_sender('text/plain', b'')
                return
            else:
                self.send_error(404)
                return
        except (IOError, KeyError, PermissionError):
            self.send_error(404)
            return

    def log_message(self, format, *args):
        try:
            with open(os.path.join(DEBUG_LOC, 'httpd.log'), 'a+') as buf:
                buf.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))
        except (IOError, PermissionError):
            pass

        if SETTINGS['Debug']:
            sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))


def check_root():
    root = True
    try:
        if SETTINGS['Root_Check']:
            root = bool(os.getuid() == 0)
    except AttributeError:
        pass

    return root


def get_lan():
    ip = ''
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        soc.connect(('10.255.255.255', 1))
        ip = str(soc.getsockname()[0])
        soc.close()
    except socket.error:
        soc.close()

    return ip


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
    version_spacing = VERSION
    while len(version_spacing) < 29:
        version_spacing += ' '
    print('#  Exploit Host v{}by Al Azif #'.format(version_spacing))
    print_line()


def ip_display():
    if SETTINGS['HTTP'] and SETTINGS['DNS']:
        server_string = 'Servers are running'
    else:
        server_string = 'Server is running'

    menu = center_menu_item('{}'.format(server_string))

    if SETTINGS['HTTP']:
        if SETTINGS['HTTP_Port'] == 80:
            menu += '\n' + center_menu_item('Your HTTP IP is {}'.format(SETTINGS['HTTP_Interface_IP']))
        else:
            menu += '\n' + center_menu_item('Your HTTP IP is {} on port {}'.format(SETTINGS['HTTP_Interface_IP'], SETTINGS['HTTP_Port']))

    if SETTINGS['DNS']:
        if SETTINGS['DNS_Port'] == 53:
            menu += '\n' + center_menu_item('Your DNS IP is {}'.format(SETTINGS['DNS_Interface_IP']))
        else:
            menu += '\n' + center_menu_item('Your DNS IP is {} on port {}'.format(SETTINGS['DNS_Interface_IP'], SETTINGS['DNS_Port']))

    print_line()
    print(menu)
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
        "Debug": False,
        "Root_Check": True,
        "Public": False,
        "DNS": True,
        "HTTP": True,
        "DNS_Interface_IP": "",
        "DNS_Port": 53,
        "HTTP_Interface_IP": "",
        "HTTP_Port": 80,
        "Compression_Level": 0,
        "UA_Check": False,
        "Theme": "default",
        "Auto_Payload": "",
        "Payload_Timeout": 60,
        "DNS_Rules": {
            "Redirect_IP": "",
            "Redirect": [
                "the.gate",
                "www.playstation.com",
                "manuals.playstation.net",
                "(get|post).net.playstation.net",
                "(d|f|h)[a-z]{2}01.(ps4|psp2).update.playstation.net",
                "update.playstation.net",
                "gs2.ww.prod.dl.playstation.net",
                "ctest.cdn.nintendo.net"
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
                ".*.sonyentertainmentnetwork.com",
                ".*.nintendo.net"
            ],
            "Pass_Through_IP": []
        },
        "Valid_UA": [
            "Mozilla/5.0 (PlayStation 4 1.01) AppleWebKit/536.26 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 1.76) AppleWebKit/536.26 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 4.05) AppleWebKit/537.78 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 4.55) AppleWebKit/601.2 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 5.51) AppleWebKit/601.2 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 5.05) AppleWebKit/601.2 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation 4 5.07) AppleWebKit/601.2 (KHTML, like Gecko)",
            "Mozilla/5.0 (PlayStation Vita 3.60) AppleWebKit/537.73 (KHTML, like Gecko) Silk/3.2",
            "Mozilla/5.0 (PlayStation Vita 3.65) AppleWebKit/537.73 (KHTML, like Gecko) Silk/3.2",
            "Mozilla/5.0 (PlayStation Vita 3.67) AppleWebKit/537.73 (KHTML, like Gecko) Silk/3.2",
            "Mozilla/5.0 (PlayStation Vita 3.68) AppleWebKit/537.73 (KHTML, like Gecko) Silk/3.2",
            "Mozilla/5.0 (Nintendo Switch; WebApplet) AppleWebKit/601.6 (KHTML, like Gecko) NF/4.0.0.6.9 NintendoBrowser/5.1.0.14936"
        ],
        "Update": {
            "PS4_No_Update": 1.76,
            "Vita_No_Update": 0.00
        }
    }


def import_settings(settings_file):
    global SETTINGS

    try:
        with open(settings_file) as buf:
            imported = json.loads(buf.read())
    except (IOError, PermissionError):
        print('ERROR: Unable to read settings.json, using defaults')
        return
    except json.decoder.JSONDecodeError:
        print('ERROR: Malformed settings.json, using defaults')
        return

    if validate_setting(imported, 'Debug', bool):
        SETTINGS['Debug'] = imported['Debug']
    else:
        print('WARNING: "Debug" in settings is invalid, using default')

    if validate_setting(imported, 'Root_Check', bool):
        SETTINGS['Root_Check'] = imported['Root_Check']
    else:
        print('WARNING: "Root_Check" in settings is invalid, using default')

    if validate_setting(imported, 'Public', bool):
        SETTINGS['Public'] = imported['Public']
    else:
        print('WARNING: "Public" in settings is invalid, using default')

    if validate_setting(imported, 'DNS', bool):
        SETTINGS['DNS'] = imported['DNS']
        if not SETTINGS['DNS']:
            print('WARNING: DNS is disabled, User\'s Manual method will not work')
    else:
        print('WARNING: "DNS" in settings is invalid, using default')

    if validate_setting(imported, 'HTTP', bool):
        SETTINGS['HTTP'] = imported['HTTP']
        if not SETTINGS['HTTP']:
            print('WARNING: HTTP is disabled, not files will be served by this host')
    else:
        print('WARNING: "HTTP" in settings is invalid, using default')

    if not SETTINGS['DNS'] and not SETTINGS['HTTP']:
        closer('ERROR: Neither the DNS or the HTTP servers are enabled')

    if validate_setting(imported, 'DNS_Interface_IP', str):
        try:
            ipaddress.ip_address(imported['DNS_Interface_IP'])
            SETTINGS['DNS_Interface_IP'] = imported['DNS_Interface_IP']
        except ValueError:
            if imported['DNS_Interface_IP']:
                print('WARNING: "DNS_Interface_IP" in settings is not a valid IP, attempting to set default')

            temp_ip = get_lan()
            if not temp_ip:
                closer('ERROR: Could not determine default for "DNS_Interface_IP"')

            if SETTINGS['DNS_Interface_IP']:
                print('INFO: "DNS_Interface_IP" set to {}'.format(SETTINGS['DNS_Interface_IP']))

            SETTINGS['DNS_Interface_IP'] = temp_ip
    else:
        print('WARNING: "DNS_Interface_IP" in settings is not a valid IP, attempting to set default')
        temp_ip = get_lan()

        if not temp_ip:
            closer('ERROR: Could not determine default for "DNS_Interface_IP"')

        if SETTINGS['DNS_Interface_IP']:
            print('INFO: "DNS_Interface_IP" set to {}'.format(SETTINGS['DNS_Interface_IP']))

        SETTINGS['DNS_Interface_IP'] = temp_ip

    if validate_setting(imported, 'DNS_Port', int) and imported['DNS_Port'] > 0 and imported['DNS_Port'] < 65535:
        SETTINGS['DNS_Port'] = imported['DNS_Port']
        if SETTINGS['DNS_Port'] != 53:
            print('WARNING: DNS is not port 53, this is for VERY advanced users only')
    else:
        print('WARNING: "DNS_Port" in settings is invalid, using default')

    if validate_setting(imported, 'HTTP_Interface_IP', str):
        try:
            ipaddress.ip_address(imported['HTTP_Interface_IP'])
            SETTINGS['HTTP_Interface_IP'] = imported['HTTP_Interface_IP']
        except ValueError:
            if imported['HTTP_Interface_IP']:
                print('WARNING: "HTTP_Interface_IP" in settings is not a valid IP, attempting to set default')

            temp_ip = get_lan()
            if not temp_ip:
                closer('ERROR: Could not determine default for "HTTP_Interface_IP"')

            if SETTINGS['HTTP_Interface_IP']:
                print('INFO: "HTTP_Interface_IP" set to {}'.format(SETTINGS['HTTP_Interface_IP']))

            SETTINGS['HTTP_Interface_IP'] = temp_ip
    else:
        print('WARNING: "HTTP_Interface_IP" in settings is not a valid IP, attempting to set default')
        temp_ip = get_lan()

        if not temp_ip:
            closer('ERROR: Could not determine default for "HTTP_Interface_IP"')

        if SETTINGS['HTTP_Interface_IP']:
            print('INFO: "HTTP_Interface_IP" set to {}'.format(SETTINGS['HTTP_Interface_IP']))

        SETTINGS['HTTP_Interface_IP'] = temp_ip

    if validate_setting(imported, 'HTTP_Port', int) and imported['HTTP_Port'] >= 1 and imported['HTTP_Port'] <= 65535:
        SETTINGS['HTTP_Port'] = imported['HTTP_Port']
        if SETTINGS['HTTP_Port'] != 80:
            print('WARNING: HTTP is not port 80, User\'s Manual method will not work')
    else:
        print('WARNING: "HTTP_Port" in settings is invalid, using default')

    if validate_setting(imported, 'Compression_Level', int) and imported['Compression_Level'] >= 0 and imported['Compression_Level'] <= 9:
        SETTINGS['Compression_Level'] = imported['Compression_Level']
    else:
        print('WARNING: "Compression_Level" in settings is invalid, using default')

    if SETTINGS['DNS_Port'] == SETTINGS['HTTP_Port'] and SETTINGS['DNS_Interface_IP'] == SETTINGS['HTTP_Interface_IP']:
        closer('ERROR: DNS and HTTP cannot share the same port on the same interface')

    if validate_setting(imported, 'UA_Check', bool):
        SETTINGS['UA_Check'] = imported['UA_Check']
    else:
        print('WARNING: "UA_Check" in settings is invalid, using default')

    if validate_setting(imported, 'Theme', str) and \
       os.path.isfile(os.path.join(THEME_LOC, imported['Theme'], 'index.html')):
            SETTINGS['Theme'] = imported['Theme']
    elif os.path.isfile(os.path.join(THEME_LOC, 'default', 'index.html')):
        closer('ERROR: "Theme" in settings is invalid, and default is missing')
    else:
        print('WARNING: "Theme" in settings is invalid, using default')

    if (validate_setting(imported, 'Auto_Payload', str) and
       os.path.isfile(os.path.join(PAYLOAD_LOC, imported['Auto_Payload']))) or \
       not imported['Auto_Payload']:
            SETTINGS['Auto_Payload'] = imported['Auto_Payload']
    else:
        print('WARNING: "Auto_Payload" in settings is invalid, using default')

    if validate_setting(imported, 'Payload_Timeout', int) and imported['Payload_Timeout'] > 0 and imported['Payload_Timeout'] < 100:
        SETTINGS['Payload_Timeout'] = imported['Payload_Timeout']
    else:
        print('WARNING: "Payload_Timeout" in settings is invalid, using default')

    if validate_setting(imported, 'DNS_Rules', dict):
        if validate_setting(imported['DNS_Rules'], 'Redirect_IP', str):
            try:
                ipaddress.ip_address(imported['DNS_Rules']['Redirect_IP'])
                SETTINGS['DNS_Rules']['Redirect_IP'] = imported['DNS_Rules']['Redirect_IP']
            except ValueError:
                if SETTINGS['DNS_Rules']['Redirect_IP']:
                    print('WARNING: "DNS_Rules[\'Redirect_IP\']" in settings is invalid, using the set "HTTP_Interface_IP": {}'.format(SETTINGS['HTTP_Interface_IP']))
                SETTINGS['DNS_Rules']['Redirect_IP'] = SETTINGS['HTTP_Interface_IP']

            if SETTINGS['HTTP_Interface_IP'] != SETTINGS['DNS_Rules']['Redirect_IP']:
                print('WARNING: DNS is not redirecting directly to this hosts HTTP server')

        if validate_setting(imported['DNS_Rules'], 'Redirect', list):
            i = 1
            temp_array = []
            for entry in imported['DNS_Rules']['Redirect']:
                if validate_setting(entry, '', str):
                    temp_array.append(entry)
                else:
                    print('WARNING: Invalid entry in "DNS_Rules[\'Redirect\']" settings, discarding rule # {}'.format(i))
                i += 1
            SETTINGS['DNS_Rules']['Redirect'] = imported['DNS_Rules']['Redirect']
        else:
            print('WARNING: "DNS_Rules[\'Redirect\']" in settings is invalid, using default')

        if validate_setting(imported['DNS_Rules'], 'Block', list):
            i = 1
            temp_array = []
            for entry in imported['DNS_Rules']['Block']:
                if validate_setting(entry, '', str):
                    temp_array.append(entry)
                else:
                    print('WARNING: Invalid entry in "DNS_Rules[\'Block\']" settings, discarding rule # {}'.format(i))
                i += 1
            SETTINGS['DNS_Rules']['Block'] = imported['DNS_Rules']['Block']
        else:
            print('WARNING: "DNS_Rules[\'Block\']" in settings is invalid, using default')

        if validate_setting(imported['DNS_Rules'], 'Pass_Through_IP', list):
            i = 1
            temp_array = []
            for entry in imported['DNS_Rules']['Pass_Through_IP']:
                if validate_setting(entry, '', str):
                    try:
                        if entry:
                            ipaddress.ip_address(entry)
                            temp_array.append(entry)
                    except ValueError:
                        print('WARNING: Invalid entry in "DNS_Rules[\'Pass_Through_IP\']" settings, discarding rule # {}'.format(i))
                else:
                    print('WARNING: Invalid entry in "DNS_Rules[\'Pass_Through_IP\']" settings, discarding rule # {}'.format(i))
                i += 1
            SETTINGS['DNS_Rules']['Pass_Through_IP'] = imported['DNS_Rules']['Pass_Through_IP']
        else:
            print('WARNING: "DNS_Rules[\'Pass_Through_IP\']" in settings is invalid, using default')
    else:
        print('WARNING: "DNS_Rules" in settings is invalid, using default')

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

    if validate_setting(imported, 'Update', dict):
        if validate_setting(imported['Update'], 'PS4_No_Update', float):
            SETTINGS['Update']['PS4_No_Update'] = imported['Update']['PS4_No_Update']
        else:
            print('WARNING: "Update[\'PS4_No_Update\']" in settings is invalid, using default')

        if validate_setting(imported['Update'], 'Vita_No_Update', float):
            SETTINGS['Update']['Vita_No_Update'] = imported['Update']['Vita_No_Update']
        else:
            print('WARNING: "Update[\'Vita_No_Update\']" in settings is invalid, using default')

    else:
        print('WARNING: "Update" in settings is invalid, using default')


def validate_setting(imported, value, type):
    try:
        if value:
            check_var = imported[value]
        else:
            check_var = imported

        if isinstance(check_var, type):
            return True
    except (KeyError, ValueError):
        pass

    return False


def generate_dns_rules():
    rules = []

    for entry in SETTINGS['DNS_Rules']['Redirect']:
        rules.append('A {} {}'.format(entry, SETTINGS['DNS_Rules']['Redirect_IP']))

    for entry in SETTINGS['DNS_Rules']['Block']:
        rules.append('A {} 0.0.0.0'.format(entry))

    return rules


def start_servers():
    if SETTINGS['DNS']:
        FAKEDNS.main(SETTINGS['DNS_Interface_IP'],
                     SETTINGS['DNS_Port'],
                     generate_dns_rules(),
                     SETTINGS['DNS_Rules']['Pass_Through_IP'],
                     SETTINGS['Debug'])
        print('>> DNS server thread is running...')

    if SETTINGS['HTTP']:
        try:
            server = ThreadedHTTPServer((SETTINGS['HTTP_Interface_IP'], SETTINGS['HTTP_Port']), MyHandler)
            thread = threading.Thread(name='HTTP_Server',
                                      target=server.serve_forever,
                                      args=(),
                                      daemon=True)
            thread.start()
            print('>> HTTP server thread is running...')
        except socket.error:
            closer('ERROR: Could not start server, is another program on tcp:{}?'.format(SETTINGS['HTTP_Port']))
        except OSError:
            print('ERROR: Could not start server, is another program on tcp:{}?'.format(SETTINGS['HTTP_Port']))
            closer('    ^^This could also be a permission error^^')
        except UnicodeDecodeError:
            print('ERROR: Python failed to get a FQDN (This is a Python Bug)')
            closer('    ^^Change your computers name to be [a-zA-Z0-9]^^')


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
        send_payload(ipaddr, 9020, SETTINGS['Payload_Timeout'], content)
        return
    elif len(payloads) <= 0 and not SETTINGS['Public']:
        print('>> No payloads in payload folder, skipping payload menu')
    elif not SETTINGS['Public']:
        MENU_OPEN = True
        payloads.insert(0, 'Don\'t send a payload')
        choice = payload_menu(payloads)
        if choice != 0:
            path = os.path.join(PAYLOAD_LOC, payloads[choice])
            print('>> Sending {}...'.format(payloads[choice]))
            with open(path, 'rb') as buf:
                content = buf.read()
            send_payload(ipaddr, 9020, SETTINGS['Payload_Timeout'], content)
        else:
            print('>> No payload sent')
        MENU_OPEN = False


def send_payload(hostname, port, timeout, content):
    soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    timeout = time.time() + timeout
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
        print('ERROR: Unable to check GitHub for updates')
        print('  ^^ Visit https://github.com/Al-Azif/ps4-exploit-host/releases/latest')
    except ValueError:
        print('WARNING: Unable to check GitHub for updates')
        print('  ^^ Visit https://github.com/Al-Azif/ps4-exploit-host/releases/latest')


def main():
    parser = argparse.ArgumentParser(description='PS4 Exploit Host')
    parser.add_argument('--settings', dest='settings', action='store',
                        default=os.path.join(CWD, 'settings.json'),
                        required=False, help='Specify a settings file')
    args = parser.parse_args()
    menu_header()

    try:
        version_check()

        default_settings()
        import_settings(args.settings)

        if not check_root():
            closer('ERROR: This must be run by root')

        start_servers()

        ip_display()

        while True:
            time.sleep(24 * 60 * 60)

    except KeyboardInterrupt:
        closer('\r>> Exiting...                                           ')


if __name__ == '__main__':
    main()

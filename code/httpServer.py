# -*- coding: utf-8 -*-

import SimpleHTTPServer
import SocketServer
import cgi
import os
import shutil
import socket
import threading
import time

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

file_downloading = []
file_uploading = []

print "work dir before:", os.getcwd()
WorkDir = os.path.split(os.path.realpath(__file__))[0]
os.chdir(WorkDir)
print "work dir now:", os.getcwd()
server_path = '/home/dev/'

file_cache = []


def findInCache(fname):
    for item in file_cache:
        if item['fname'] == fname:
            return item


class MyHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    restart_server_mutex = threading.Lock()

    def copyfileobj(self, fsrc, fdst, length=16 * 1024):
        size = 0
        while 1:
            buf = fsrc.read(length)
            if not buf:
                break
            size += len(buf)
            fdst.write(buf)

    def copyfile(self, source, outputfile):
        if source.__class__ == file:
            fname = source.name
            if fname.endswith('.apk') or fname.endswith('.ipa'):
                cacheinfo = findInCache(fname)
                if not cacheinfo:
                    self.log_message('cache file: %s', fname)
                    data = StringIO()
                    shutil.copyfileobj(source, data)
                    cacheinfo = {'fname': fname, 'datastr': data.getvalue()}
                    file_cache.insert(0, cacheinfo)

                    if len(file_cache) > 2:
                        del file_cache[2:]

                fcache = StringIO(cacheinfo['datastr'])
                fcache.seek(0)
                self.copyfileobj(fcache, outputfile)
                time.sleep(2.0)
                fcache.close()
                return

        self.copyfileobj(source, outputfile)

    def send_file(self):
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            if not self.path.endswith('/'):
                # redirect browser - doing basically what apache does
                self.send_response(301)
                self.send_header("Location", self.path + "/")
                self.end_headers()
                return None
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                f = self.list_directory(path)
                self.copyfile(f, self.wfile)
                f.close()
                return
        ctype = self.guess_type(path)
        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = open(path, 'rb')
        except IOError:
            self.send_error(404, "File not found")
            return None
        self.send_response(200)
        self.send_header("Content-type", ctype)

        fs = os.fstat(f.fileno())
        range = self.headers.get('Range', "")
        hasRange = False
        if range and range.startswith('bytes='):
            range = range[6:]
            pos = range.find('-')
            if pos >= 0:
                startBytes = int(range[0:pos])
                endBytes = range[pos + 1:]
                if endBytes:
                    endBytes = int(endBytes)
                else:
                    f.seek(0, 2)
                    endBytes = f.tell()
                    f.seek(0, 0)
            contentLen = endBytes - startBytes + 1
            f.seek(startBytes, 0)
            self.send_header("Content-Range", 'bytes %d-%d/%d' % (startBytes, endBytes, fs[6]))
            hasRange = True
        else:
            contentLen = fs[6]
        self.send_header("Content-Length", str(contentLen))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()

        if hasRange:
            size = 0
            while size < contentLen:
                length = min(contentLen - size, 8 * 1024)
                buf = f.read(length)
                if not buf:
                    break
                size += len(buf)
                self.wfile.write(buf)
        else:
            self.copyfile(f, self.wfile)
        f.close()

    def do_GET(self):

        if self.path == '/reload':
            self.send_response(200)
            encoding = 'utf8'
            self.send_header("Content-type", "text/html; charset=%s" % encoding)
            self.send_header("Content-Length", "-1")
            self.end_headers()

            f = self.wfile
            f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
            f.write("<html>\n<title>reload服务器</title>\n")
            f.write("<body>")

            if self.restart_server_mutex.acquire(False):
                try:
                    fileObj = os.popen('sh %sbin/update_and_reload.sh 2>&1' % (server_path,))
                    data = fileObj.read(100)
                    while data:
                        data = data.replace('\n', '<br/>')
                        f.write(data)
                        f.flush()
                        data = fileObj.read(100)
                    fileObj.close()
                finally:
                    self.restart_server_mutex.release()
            else:
                f.write('其他人正在reload服务器。。。' + '\n')

            f.write("<hr>\n<ul>\n")
            f.write("</ul>\n<hr>\n</body>\n</html>\n")
            f.flush()
        elif self.path.startswith('/real_time_log?'):
            logName = self.path.split('=')[1]

            self.send_response(200)
            encoding = 'utf8'
            self.send_header("Content-type", "text/html; charset=%s" % encoding)
            self.send_header("Content-Length", "-1")
            self.end_headers()

            f = self.wfile
            f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
            f.write("<html>\n<title>实时日志:%s</title>\n" % (logName,))
            f.write("<body>")

            finename = server_path + 'log/log.' + logName
            print finename
            fileobj = open(finename)
            if fileobj:
                fileobj.seek(0, 2)
                currSize = fileobj.tell()
                while True:
                    fileobj.seek(0, 2)
                    newSize = fileobj.tell()
                    if newSize > currSize:
                        fileobj.seek(currSize, 0)
                        currSize = newSize
                        data = fileobj.read()
                        if data:
                            data = data.replace('\n', '<br/>')
                            f.write(data)
                    elif newSize < currSize:
                        currSize = newSize

                    connection = self.connection
                    try:
                        connection.settimeout(0.2)
                        datas = connection.recv(8192)
                        if not datas:
                            print 'closed !!!!!!!!!!!'
                            break
                    except socket.timeout:
                        pass

                    time.sleep(1)

            f.write("<hr>\n<ul>\n")
            f.write("</ul>\n<hr>\n</body>\n</html>\n")
            f.flush()
        elif self.path.startswith('/del_file_list?'):
            currpath = self.path[self.path.index("?") + 1:]
            self.send_response(200)
            encoding = 'utf8'
            self.send_header("Content-type", "text/html; charset=%s" % encoding)
            self.send_header("Content-Length", "-1")
            self.end_headers()

            f = self.wfile
            f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
            f.write("<html>\n<title>删除文件: %s</title>\n" % (currpath,))
            f.write("<body>")

            if currpath:
                f.write('<p><a href="/del_file_list?%s">返回</a></p>' % (os.path.dirname(currpath)))

            absCurrPath = os.path.join(WorkDir, currpath)
            absCurrPath = os.path.realpath(absCurrPath)
            itemlist = os.listdir(absCurrPath)
            for item in itemlist:
                thispath = os.path.join(currpath, item)
                if os.path.isdir(thispath):
                    f.write('<p><a href="/del_file_list?%s">进入   %s</a> <a href="/del_file?%s">删除目录</a></p>' % (
                        thispath, item, thispath))
                else:
                    f.write('<p><a href="/del_file?%s">删除   %s</a></p>' % (thispath, item))

            f.write("<hr>\n<ul>\n")
            f.write("</ul>\n<hr>\n</body>\n</html>\n")
            f.flush()
        elif self.path.startswith('/del_file?'):
            currpath = self.path[self.path.index("?") + 1:]

            absCurrPath = os.path.join(WorkDir, currpath)
            absCurrPath = os.path.realpath(absCurrPath)

            try:
                if os.path.isdir(absCurrPath):
                    os.rmdir(absCurrPath)
                else:
                    os.remove(absCurrPath)
            except Exception, e:
                self.send_response(200)
                encoding = 'utf8'
                self.send_header("Content-type", "text/html; charset=%s" % encoding)
                self.send_header("Content-Length", "-1")
                self.end_headers()

                f = self.wfile
                f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
                f.write("<html>\n<title>删除文件失败</title>\n")
                f.write("<body>")

                f.write('<p>删除文件失败: %s %s</p>' % (currpath, str(e),))

                f.write("<hr>\n<ul>\n")
                f.write("</ul>\n<hr>\n</body>\n</html>\n")
                f.flush()
            else:
                self.send_response(301)
                self.send_header("Location", "/del_file_list?%s" % (os.path.dirname(currpath),))
                self.end_headers()

                f = self.wfile

                f.flush()
        elif self.path == '/show_dump':
            self.send_response(200)
            encoding = 'utf8'
            self.send_header("Content-type", "text/html; charset=%s" % encoding)
            self.send_header("Content-Length", "-1")
            self.end_headers()

            f = self.wfile
            f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
            f.write("<html>\n<title>show_dump</title>\n")
            f.write("<body>")

            from showDump import show_dump
            show_dump('hello', 'world')

            f.write("<hr>\n<ul>\n")
            f.write("</ul>\n<hr>\n</body>\n</html>\n")
            f.flush()
        else:
            self.send_file()

    def do_POST(self):
        # self.log_message('start post: %s', repr(self.headers))
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST',
                     'CONTENT_TYPE': self.headers['Content-Type'],
                     })
        filename = form['fname'].filename
        savename = None
        if 'newname' in form:
            savename = form['newname'].value
        if not savename:
            savename = filename

        path = self.translate_path(self.path)
        filepath = os.path.join(path, savename)
        dirpath = os.path.split(filepath)[0]
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        savefile = open(filepath, 'wb')
        filedata = form['fname'].value
        savefile.write(filedata)
        savefile.close()

        cacheinfo = findInCache(filepath)
        if cacheinfo:
            self.log_message('post file update cache: %s', filepath)
            cacheinfo['datastr'] = filedata

        self.log_message('upload file succ: %s %d', savename, len(filedata))

        f = StringIO()
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write("<html>\n<title>上传文件成功</title>\n")
        f.write("<body>\n<h2>上传文件成功, name: %s, size: %d</h2>\n" % (savename, len(filedata)))
        f.write("<hr>\n<ul>\n")

        f.write("</ul>\n<hr>\n</body>\n</html>\n")
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        encoding = 'utf8'
        self.send_header("Content-type", "text/html; charset=%s" % encoding)
        self.send_header("Content-Length", str(length))
        self.end_headers()
        self.copyfile(f, self.wfile)


PORT = 9080

Handler = MyHandler
httpd = SocketServer.ThreadingTCPServer(("", PORT), Handler)
print "serving at port", PORT
httpd.serve_forever()

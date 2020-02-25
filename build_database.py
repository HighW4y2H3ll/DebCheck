#!/usr/bin/python3

import os
import gzip
import time
import shutil
import fnmatch
import requests
import tempfile
import subprocess
import multiprocessing
from multiprocessing.managers import BaseManager

import database

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(CUR_DIR, "workspace")
DATABASE_DIR = os.path.join(WORK_DIR, "pkgdb")
TEMP_DIR = os.path.join(WORK_DIR, "temp")

os.makedirs(DATABASE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

url_list = [
        ["http://http.us.debian.org/debian/", "buster", "mipsel", "main"],
        ["http://http.us.debian.org/debian/", "buster", "mips64el", "main"],
        ["http://http.us.debian.org/debian/", "buster", "mips", "main"],
        ["http://http.us.debian.org/debian/", "buster", "armel", "main"],
        ["http://http.us.debian.org/debian/", "buster", "armhf", "main"],
        ["http://http.us.debian.org/debian/", "buster", "arm64", "main"],
        #["http://http.us.debian.org/debian/", "sid", "mips", "main"],
        #["http://archive.debian.org/debian/", "buster", "mips", "main"],
        ]

def build_list(baseurl, dist, arch, comp):
    url = f"{baseurl}dists/{dist}/{comp}/binary-{arch}/Packages.gz"
    r = requests.get(url)
    pkglist = gzip.decompress(r.content).decode('latin-1')
    pkgs = {}
    for x in pkglist.split('\n'):
        if x.startswith("Package:"):
            seenpkg = f"{arch}_{x[8:].strip()}"
        #elif x.startswith("Version:"):
        #    seenpkg = f"{seenpkg}_{x[8:].strip()}"
        elif x.startswith("Filename:"):
            pkgs[seenpkg] = f"{baseurl}{x[9:].strip()}"
    #for x,y in pkgs.items():
    #    print(f"{x} : {y}")
    return pkgs

def pkg_worker(pkg, fileurl, db):
    ELF_MAGIC = b"\x7f\x45\x4c\x46"
    cwd = tempfile.mkdtemp(dir=TEMP_DIR)

    r = requests.get(fileurl)
    while not r.ok:
        time.sleep(0.1)
        r = requests.get(fileurl)

    debpath = os.path.join(cwd, f"{pkg}.deb")
    with open(debpath, 'wb') as fd:
        fd.write(r.content)

    unpackcmd = ["dpkg", "-x", debpath, "./tmp"]
    subprocess.check_call(unpackcmd, cwd=cwd)

    for root, dirs, files in os.walk(os.path.join(cwd, "tmp")):
        for fn in files:
            ff = os.path.join(root, fn)

            # skip symbolic link
            if os.path.islink(ff):
                continue

            with open(ff, 'rb') as fd:
                if fd.read(4) == ELF_MAGIC:
                    dbdir = os.path.join(DATABASE_DIR, pkg)
                    final_f = os.path.join(dbdir, os.path.basename(ff))

                    os.makedirs(dbdir, exist_ok=True)
                    os.rename(ff, final_f)

                    db.waitinsert(database.Packages(
                        pkgname=pkg,
                        url=fileurl,
                        filepath=ff))

    shutil.rmtree(cwd)


#import logging
#mpl = multiprocessing.log_to_stderr()
#mpl.setLevel(logging.DEBUG)

pkgs = {}
for urltup in url_list:
    pkgs.update(build_list(*urltup))

#pkgs = {"alien-arena-server": "alien-arena-server_7.66+dfsg-5_amd64.deb"}
pool = multiprocessing.Pool()

BaseManager.register('DB', database.Database)

manager = BaseManager()
manager.start()
db = manager.DB()
result = [ \
        pool.apply_async(pkg_worker, args=(pkg, fileurl, db)) \
        for pkg, fileurl in pkgs.items() \
        ]

pool.close()
pool.join()

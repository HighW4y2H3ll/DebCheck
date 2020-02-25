#!/usr/bin/python3

import os
import shutil
import fnmatch
import tempfile
import subprocess
import multiprocessing

import database

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(CUR_DIR, "workspace")
DATABASE_DIR = os.path.join(WORK_DIR, "pkgdb")
TEMP_DIR = os.path.join(WORK_DIR, "temp")

os.makedirs(DATABASE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

url_list = [
        "http://http.us.debian.org/debian/dists/buster/main/binary-all/Packages.gz",
        "http://http.us.debian.org/debian/dists/buster/non-free/binary-all/Packages.gz",
        "http://http.us.debian.org/debian/dists/buster/contrib/binary-all/Packages.gz",
        ]

def build_list(url):
    cmd = ["curl", url, "|", "gunzip"]
    fetcher = subprocess.Popen(" ".join(cmd), shell=True, stdout=subprocess.PIPE)
    pkglist = fetcher.stdout.read().decode('latin-1')
    pkgs = {}
    for x in pkglist.split('\n'):
        if x.startswith("Package:"):
            seenpkg = x[8:].strip()
        elif x.startswith("Filename:"):
            pkgs[seenpkg] = os.path.basename(x[8:].strip())
    #for x,y in pkgs.items():
    #    print(f"{x} : {y}")
    return pkgs

def pkg_worker(pkg, debname):
    ELF_MAGIC = b"\x7f\x45\x4c\x46"
    cwd = tempfile.mkdtemp(dir=TEMP_DIR)

    fetchcmd = ["apt", "download", pkg]
    subprocess.check_call(fetchcmd, cwd=cwd)

    subfilelist = fnmatch.filter(os.listdir(cwd), "*.deb")
    assert(len(subfilelist) == 1)

    if debname not in subfilelist:
        debname = subfilelist[0]

    unpackcmd = ["dpkg", "-x", debname, "./tmp"]
    subprocess.check_call(unpackcmd, cwd=cwd)

    for root, dirs, files in os.walk(os.path.join(cwd, "tmp")):
        for fn in files:
            ff = os.path.join(root, fn)
            with open(ff, 'rb') as fd:
                if fd.read(4) == ELF_MAGIC:
                    dbdir = os.path.join(DATABASE_DIR, pkg)
                    final_f = os.path.join(dbdir, os.path.basename(ff))

                    os.makedirs(dbdir, exist_ok=True)
                    os.rename(ff, final_f)

                    db = database.Database()
                    db.newsession()
                    db.insert(database.Packages(
                        pkgname=pkg,
                        debname=debname,
                        filepath=ff))
                    db.closesession()

    shutil.rmtree(cwd)


#import logging
#mpl = multiprocessing.log_to_stderr()
#mpl.setLevel(logging.DEBUG)

pkgs = {}
for url in url_list:
    pkgs.update(build_list(url))

#pkgs = {"alien-arena-server": "alien-arena-server_7.66+dfsg-5_amd64.deb"}
pool = multiprocessing.Pool()

# probe database first to make sure database/tables are created
db = database.Database()
result = [ \
        pool.apply_async(pkg_worker, args=(pkg, debname)) \
        for pkg, debname in pkgs.items() \
        ]

pool.close()
pool.join()

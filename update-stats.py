#!/usr/bin/env python2

import argparse
import flathub
import json
import sys
import os.path

refs_cache = {}

def ref_to_id(ref):
    parts = ref.split("/")
    if parts[0] == "app":
        return parts[1]
    if parts[0] == "runtime" and not (parts[1].endswith(".Debug") or parts[1].endswith(".Locale") or parts[1].endswith(".Sources")):
        return "%s/%s" % (parts[1], parts[3])
    return None

class InstallInfo:
    def __init__(self):
        self.arch = {}

    def add(self, ref):
        parts = ref.split("/")
        arch = parts[2]
        self.arch[arch] = self.arch.get(arch, 0) + 1

    def from_dict(self, dct):
        self.arch = dct['arch']

class DayInfo:
    def __init__(self, date):
        self.date = date
        self.downloads = 0
        self.delta_downloads = 0
        self.ostree_versions = {}
        self.flatpak_versions = {}
        self.installs = {}

    def from_dict(self, dct):
        self.downloads = dct['downloads']
        self.delta_downloads = dct['delta_downloads']
        self.ostree_versions = dct['ostree_versions']
        self.flatpak_versions = dct['flatpak_versions']
        installs = dct['installs']
        for id in installs:
            i = self.get_install(id)
            i.from_dict(installs[id])

    def get_install(self, id):
        if not id in self.installs:
            self.installs[id] = InstallInfo()
        return self.installs[id]

    def add(self, download):
        checksum = download[flathub.CHECKSUM]
        ref = refs_cache[checksum]

        if not ref:
            return

        id = ref_to_id (ref);
        if not id:
            return

        i = self.get_install(id)
        i.add(ref)

        self.downloads = self.downloads + 1
        if download[flathub.IS_DELTA]:
            self.delta_downloads = self.delta_downloads + 1

        ostree_version = download[flathub.OSTREE_VERSION]
        self.ostree_versions[ostree_version] = self.ostree_versions.get (ostree_version, 0) + 1

        flatpak_version = download[flathub.FLATPAK_VERSION]
        if flatpak_version:
            self.flatpak_versions[flatpak_version] = self.flatpak_versions.get (flatpak_version, 0) + 1

def load_dayinfo(dest, date):
    day = DayInfo(date)
    path = os.path.join(dest, date + ".json")
    if os.path.exists(path):
        day_f = open(path, 'r')
        dct = json.loads(day_f.read ())
        day_f.close()
        day = DayInfo(dct['date'])
        day.from_dict(dct)
    return day

parser = argparse.ArgumentParser()
parser.add_argument("--dest", type=str, help="path to destination dir", default="stats")
parser.add_argument("logfiles", metavar='LOGFILE', type=str, help="path to log file", nargs='+')
args = parser.parse_args()

try:
    f = open('ref-cache.json', 'r')
    refs_cache = json.loads(f.read ())
except:
    pass

downloads = []
for logname in sys.argv[1:]:
    d = flathub.parse_log(logname)
    downloads = downloads + d

cache_modified = False
for d in downloads:
    if d[flathub.REF] and d[flathub.CHECKSUM] not in refs_cache:
        cache_modified = True
        refs_cache[d[flathub.CHECKSUM]] = d[flathub.REF]

for d in downloads:
    if d[flathub.CHECKSUM] not in refs_cache:
        cache_modified = True
        refs_cache[d[flathub.CHECKSUM]] = flathub.resolve_commit(d[flathub.CHECKSUM])

if cache_modified:
    try:
        f = open('ref-cache.json', 'w')
        json.dump(refs_cache, f)
        f.close()
    except:
        pass

days = {}

for d in downloads:
    date = d[flathub.DATE]
    day = days.get(date, None)
    if not day:
        day = load_dayinfo(args.dest, date)
        days[date] = day
    day.add(d)

for date in days:
    day=days[date]
    path = os.path.join(args.dest, date + ".json")
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        os.makedirs(directory, 0755)
    f = open(path, 'w')
    json.dump(day, f, default=lambda x: x.__dict__, sort_keys = True)
    f.close()

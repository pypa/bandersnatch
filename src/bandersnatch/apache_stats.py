from bandersnatch import apache_reader
import bz2
import csv
import gzip
import os
import re
import socket
import urllib2


from apache_reader import ApacheLogReader


class LocalStats(object):
    """Base class that writes the log file
    """
    def _get_logs(self, logfile, file_urls):
        """Needs to return an iterator. Each entry
        should be a dictionary"""
        if callable(logfile):
            return logfile(file_urls)
        raise NotImplementedError

    def _get_file_obj(self, path, mode='r', compression=None):
        """returns a file object"""
        if compression == 'bz2':
            return bz2.BZ2File(path, mode)
        elif compression == 'gz':
            return gzip.open(path, mode)
        return open(path, mode)

    def _build_stats(self, logfile, fileobj, files_url='/packages',
                     filter=None, compression=None):
        """Builds a stats file

        - logfile: path to the original log file, or callable
        - fileobj : a file object or a path to create a file
        - files_url : a filter that define the beginnin of package urls
        - filter: if given, a callable that receives the
        current line. if the callable returns True,
        the line is not included
        """
        if isinstance(fileobj, str):
            fileobj = self._get_file_obj(fileobj, 'w', compression)
            file_created = True
        else:
            file_created = False

        writer = csv.writer(fileobj)
        downloads = {}
        for log in self._get_logs(logfile, files_url):
            if filter is not None:
                if filter(log):
                    continue
            filename = log['filename']
            user_agent = log['useragent']
            package_name = log['packagename']
            key = (filename, user_agent, package_name)
            count = log.get('count', 1)
            if key in downloads:
                downloads[key] += count
            else:
                downloads[key] = count
        filenames = downloads.keys()
        filenames.sort()
        for key in filenames:
            filename, user_agent, package_name = key
            count = downloads[key]
            writer.writerow((package_name, filename, user_agent, count))
        if file_created:
            fileobj.close()

    def build_daily_stats(self, year, month, day, logfile, fileobj,
                          files_url='/packages', compression=None):
        """creates a daily stats file using an apache log file.

        - year, month, day: values for the day
        - logfile : path to the log file, or callable
        - fileobj : a file object or a path to create a file
        - files_url : a filter that define the beginning of package urls
        """
        def _filter(log):
            return (day != log['day'] or month != log['month'] or
                    year != log['year'])

        self._build_stats(logfile, fileobj, files_url, _filter, compression)

    def build_monthly_stats(self, year, month, logfile, fileobj,
                            files_url='/packages', compression=None):
        """creates a monthly stats file using an apache log file.

        - year, month: values for the month
        - logfile : path to the log file
        - fileobj : a file object or a path to create a file
        - files_url : a filter that define the beginnin of package urls
        """
        def _filter(log):
            return (month != log['month'] or year != log['year'])

        self._build_stats(logfile, fileobj, files_url, _filter, compression)

    def read_stats(self, stats_file):
        """Returns an iterator over a stats file"""
        if isinstance(stats_file, str):
            ext = os.path.splitext(stats_file)[-1][1:]
            stats_file = self._get_file_obj(stats_file, 'r', ext)
        reader = csv.reader(stats_file)
        for line in reader:
            yield {'packagename': line[0],
                   'filename': line[1],
                   'useragent': line[2],
                   'count': line[3]}
        #reader.close()

    def build_local_stats(self, year, month, day, logfile, directory=None):
        """builds local stats with default values"""
        filename = '%d-%.2d-%.2d.bz2' % (year, month, day)
        if directory is not None:
            filename = os.path.join(directory, filename)

        self.build_daily_stats(year, month, day, logfile, filename,
                               compression='bz2')


class ApacheLocalStats(LocalStats):
    """concrete class that uses the ApacheLogReader"""

    def _get_logs(self, logfile, files_url):
        return ApacheLogReader(logfile, files_url)


class ApacheDistantLocalStats(ApacheLocalStats):
    """Concrete class that gets the data from a distant file"""
    is_url = re.compile(r'^http://')

    def __init__(self, cache_folder='', timeout=5):
        self.cache_folder = cache_folder
        if not os.path.exists(cache_folder):
            os.makedirs(cache_folder)
        self.timeout = timeout

    def get_and_cache(self, url):
        """retrieve the distant file and add it in the local cache"""
        basename = url.split('/')[-1]
        filename = os.path.join(self.cache_folder, basename)
        if os.path.exists(filename):
            # in cache, let's return it
            return filename, open(filename)

        # not in cache, we need to retrieve it
        # and store it
        oldtimeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(self.timeout)
        try:
            try:
                content = urllib2.urlopen(url).read()
            except (urllib2.URLError, socket.timeout):
                return '', None
        finally:
            socket.setdefaulttimeout(oldtimeout)

        f = open(filename, 'w')
        try:
            f.write(content)
        finally:
            f.close()

        return filename, open(filename)

    def read_stats(self, stats_file):
        """retrieve a distant file and works with it"""
        if self.is_url.search(stats_file) is not None:
            path, fileobj = self.get_and_cache(stats_file)
            if path == '':
                return iter([])
        return ApacheLocalStats.read_stats(self, path)


def update_stats(statsdir, logs):
    days = set()
    records = []
    for fn in logs:
        for record in apache_reader.ApacheLogReader(fn, files_url='/packages'):
            days.add((record['year'], record['month'], record['day']))
            records.append(record)

    days = sorted(days)[1:-1]

    class Stats(LocalStats):
        def _get_logs(self, logfile, files_url):
            return records
    stats = Stats()
    for year, month, day in days:
        stats.build_local_stats(year, month, day, None,
                                os.path.join(statsdir, 'days'))

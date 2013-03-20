"""
Reads apache log files
"""
import bz2
import gzip
import re
import os

# list of recognized user agents
SETUPTOOLS_UA = (re.compile((r'^.* setuptools/(?P<version>[0-9]\..*)$')),
                 'setuptools/%s')
URLLIB_UA = (re.compile(r'^Python-urllib/(?P<version>[23]\.[0-9])$'),
             'Python-urllib/%s')
SAFARI_UA = (re.compile(r'^Mozilla.* .* Version/(?P<version>.*) Safari/.*$'),
             'Safari/%s')
GOOGLEBOT = (re.compile(r'Googlebot-Mobile/(?P<version>.*);'),
             'Googlebot-Mobile/%s')
MSNBOT = (re.compile(r'^msnbot/(?P<version>.*) '), 'msnbot/%s')
FIREFOX_UA = (re.compile(r'^Mozilla.*? Firefox/(?P<version>[23])\..*$'),
              'Firefox/%s')
PLAIN_MOZILLA = (re.compile(r'^Mozilla/(?P<version>.*?) '),
                 'Mozilla/%s')

logre = re.compile(
    r"\[(?P<day>..)/(?P<month>...)/(?P<year>....):"
    r"(?P<hour>..):(?P<min>..):(?P<sec>..) "
    r'(?P<zone>.*)\] "GET (?P<path>[^ "]+) HTTP/1.." 200 .*? (?:".*?")? '
    r'"(User-Agent: )?(?P<useragent>.*)"$', re.DOTALL)

month_names = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
               'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
month_index = {}

for i in range(12):
    month_index[month_names[i]] = i+1


def month_to_index(month):
    return month_index[month.lower()]


class ApacheLogReader(object):
    """provides an iterator over apache logs"""

    def __init__(self, filename, files_url='', mode=None):
        if mode is None:
            ext = os.path.splitext(filename)[-1]
            if ext in ('.bz2', '.gz'):
                mode = 'r:%s' % ext[1:]
            else:
                mode = 'r'
        if ':' in mode:
            mode, compr = mode.split(':')
        else:
            mode, compr = mode, None
        if compr not in ('bz2', 'gz', None):
            raise ValueError('%s mode not supported' % compr)
        if compr == 'bz2':
            self._data = bz2.BZ2File(filename, mode)
        elif compr == 'gz':
            self._data = gzip.open(filename)
        else:
            self._data = open(filename, mode)

        self.files_url = files_url

    def __iter__(self):
        return self

    def package_name(self, path):
        path = [p for p in path.split('/') if p != '']
        return path[-2]

    def get_simplified_ua(self, user_agent):
        """returns a simplified version of the user agent"""
        for expr, repl in (URLLIB_UA, SETUPTOOLS_UA, SAFARI_UA, GOOGLEBOT,
                           MSNBOT, FIREFOX_UA, PLAIN_MOZILLA):
            res = expr.search(user_agent)
            if res is not None:
                return repl % res.group('version')
        return user_agent

    def next(self):

        while True:
            line = self._data.next().strip()
            m = logre.search(line)
            if m is None:
                continue
            path = m.group('path')
            filename = os.path.basename(path)
            filename = filename.split('?')[0]
            if not path.startswith(self.files_url) or filename == '':
                continue
            res = m.groupdict()
            res['month'] = month_to_index(res['month'])
            res['useragent'] = self.get_simplified_ua(res['useragent'])
            res['filename'] = filename
            res['packagename'] = self.package_name(path)
            res['day'] = int(res['day'])
            res['year'] = int(res['year'])
            res['hour'] = int(res['hour'])
            res['minute'] = int(res['min'])
            return res

        raise StopIteration

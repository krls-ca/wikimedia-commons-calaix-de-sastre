import locale
import re
import time

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Literal, NewType, NoReturn, Optional, Tuple, Union, Any
from dateutil.relativedelta import relativedelta

from pywikibot import Page, Site, pagegenerators, User, Timestamp

"""
Nou bot arxivador de pàgines de discussions.

Vegeu documentació a [[User:ArxivaBot/Documentació]]

"""


@dataclass
class Patterns:
    algo = re.compile(r'(?P<func>old|done)\((?P<value>\d{1,2})(?P<unit>[ywdhs])\)')
    date = re.compile(r'(?P<time>\d{2}:\d{2}), (?P<day>\d{1,2}) (?P<month>\w{3,4}) (?P<year>\d{4})')
    done = re.compile(r'\{\{ *(?:[Ff]et|[Nn]o fet|[Tt]ancat) *(\|.*?)??\}\}')
    size = re.compile(r'(?P<value>\d{1,3}(?: \d{3})+|\d+) *(?P<unit>[BkKMT]?)')
    table_row = re.compile(
        r"\| *(?P<page>.+?) *\|\| *(?P<archive>.+?) *\|\| *(?P<algo>.+?) *\|\| *(?P<maxarchivesize>.+?) *\|\| *"
        r"(?P<minthreadsleft>.+?) *\|\| *(?P<minthreadstoarchive>.+?) *\|\| *(?:<nowiki>)?(?P<archiveheader>.+?)"
        r"(?:</nowiki>)?? *(?:\n\n *(?P<key>.+?) *)?\n"
    )
    threads = re.compile(r'\n==\s*(?P<title>.+?)\s*?==')


class Utils:
    def __init__(self):
        self.patterns = Patterns()
        self.month_dict = {}
        self.reldelta_keys = {
            'y': {'en': 'years', 'ca': 'anys'},
            'm': {'en': 'months', 'ca': 'mesos'},
            'w': {'en': 'weeks', 'ca': 'setmanes'},
            'd': {'en': 'days', 'ca': 'dies'},
            'h': {'en': 'hours', 'ca': 'hores'},
            'i': {'en': 'minutes', 'ca': 'minuts'},
            's': {'en': 'seconds', 'ca': 'segons'}
        }

    def set_month_dict(self):
        _sys_months = [time.strftime("%b", time.strptime(f"01-{_:>02}-2023", "%d-%m-%Y")) for _ in range(1, 13)]
        _wiki_months = [short for long, short in site.months_names]
        self.month_dict = dict(zip(_wiki_months, _sys_months))

    def get_datetime(self, dt):
        """
        date_str té format Wikimedia, els mesos no tenen punt final, agost es 'ago' en lloc de 'ag.'
        :param dt:
        :return:
        """
        time_str, day, month, year = dt
        month = self.month_dict[month]
        return datetime.strptime(f'{time_str}, {day} {month} {year}', '%H:%M, %d %b %Y')

    @staticmethod
    def join_str_list(lst: List[str]):
        return f"[[{']], [['.join(lst[:-1])}{']] i [[' if len(lst) > 1 else ''}{lst[-1]}]]"

    def run(self):
        self.set_month_dict()


# globals
locale.setlocale(locale.LC_TIME, 'ca_AD.UTF-8')
site = Site('ca', 'wikipedia', 'KRLS Bot')
utils = Utils()
utils.set_month_dict()
Unit = NewType('Unit', Literal['B', 'K', 'k', 'T'])


class Algo:
    def __init__(self):
        self.function = ''
        self.value = 0
        self.unit = ''

    def __repr__(self):
        return f'<Algo {self.function} {self.value} {self.unit}>'

    @property
    def summary(self):
        period = utils.reldelta_keys.get(self.unit)['ca']
        return f'(més antic de {self.value} {period})'

    def set(self, string):
        match = utils.patterns.algo.search(string)
        if match:
            self.function = match.group('func')
            self.value = int(match.group('value'))
            self.unit = match.group('unit')


class Summary:
    def __init__(self, source: str):
        self.current_threads = 0
        self.source = source
        self.thread_list = []
        self.target_list = []
        self.algo: Optional[Algo] = None

    @property
    def insert_message(self):
        return f'Bot: arxivant {self.current_threads} fils de discussió de [[{self.source}]].'

    @property
    def remove_message(self):
        return f'Bot: arxivats {len(self.thread_list)} fils de discussió {self.algo.summary} a {utils.join_str_list(self.target_list)}'

    def add_target(self, target: str):
        self.target_list.append(target)

    def add_threads(self, threads: List[str]):
        self.current_threads = len(threads)
        self.thread_list.extend(threads)


class Size:
    def __init__(self, value: int = 200, unit: Unit = 'K'):
        self.value: int = value
        self.unit: Unit = unit

        # read maxarticlesize
        try:
            # keep a gap of 1 KB not to block later changes
            self.real_max_size = site.siteinfo['maxarticlesize'] - 1024
        except KeyError:  # mw < 1.28
            self.real_max_size = 2_096_128  # 2 MB - 1 KB gap

    def __repr__(self):
        return f'<Size {self.value} {self.unit}>'

    def set(self, string) -> NoReturn:
        """
        Return a size for a shorthand size.

        Accepts a string defining a size::

          1337 - 1337 bytes
          150K - 150 kilobytes
          2M - 2 megabytes

        Set attribute max_size: a Size Type object (value, unit), where `value` is an integer and
            unit is `B` (bytes) or `T` (threads).
        """
        match = utils.patterns.size.fullmatch(string if string else '-')
        if not match:
            return self.set(f'{self.value} {self.unit}')
        val, unit = match.groups()
        val = int(val.replace(' ', ''))

        if unit == 'M':
            val *= 1024 ** 2
        elif unit.lower() == 'k':
            val *= 1024

        if unit != 'T':
            unit = 'B'

        if unit == 'B' and val > self.real_max_size:
            val = self.real_max_size

        self.value = val
        self.unit = unit

    def to_int(self):
        """
        Per a mantenir l'objectiu original, convertim el nombre sencer a negatiu quan es tracta del nombre de
        fils que s'aporta amb la lletra T. K i k es multipliquen per 1024, B no suposa cap canvi.
        :param size:
        :return:
        """
        if self.unit not in 'BKkT':
            raise AttributeError(f'MaxArchiveSize Exception unkown "{self.unit}" unit. Allowed units are: B, K, k, T.')
        elif self.unit == 'T':
            return -self.value
        return self.value


class TargetConfig:
    def __init__(self):
        self.title: str = ''
        self.bared_title = ''
        self.header: str = ''
        self.max_size: Size = Size()
        self.min_threads_to_archive = 2
        self.key: str = ''  # Only for MiszaBot Config Compatibility
        self.last_counter: int = 0
        self.standard_items = (
            'counter', 'year', 'month', 'monthname', 'monthnameshort', 'isoyear', 'isoweek', 'semester', 'quarter',
            'week', 'localcounter', 'localyear', 'localisoyear', 'localisoweek', 'localsemester', 'localquarter',
            'localmonth', 'localweek'
        )
        self.std_time_items = self.standard_items[1:]

    def __repr__(self):
        return f'<TargetConfig title: "{self.title}" max_size: {self.max_size}, last_counter: {self.last_counter}>'

    @property
    def has_counter(self):
        return self.last_counter != 0

    @property
    def base_title(self) -> str:
        title = self.title.replace('_', ' ')
        for item in self.standard_items:
            title = title.replace(f'{{{item}}}', '')
        return title

    @property
    def has_time_param(self):
        return any([item in self.bared_title for item in self.std_time_items])

    @property
    def title_tail(self):
        tail = self.title.split('/')[-1].replace('_', ' ')
        for item in self.standard_items:
            tail = tail.replace(f'{{{item}}}', '')
        return tail

    def inc_counter(self):
        self.last_counter += 1

    def get_counter(self) -> str:
        """
        Es tracta d'obtenir el darrer número d'arxiu quan siga /Arxiu_{counter}
        self.archive_base és el nom de la pàgina (title) sense '{counter}'.
        :return: int
        """
        numbers = [
            int(re.search(r'/%(tail)s(\d+)' % {'tail': self.title_tail}, page.title(without_brackets=True)).group(1))
            for page in pagegenerators.PrefixingPageGenerator(self.base_title, includeredirects=False, site=site)
            if page.title(without_brackets=True)[-1].isdigit()
        ]
        if not numbers:
            # raise IndexError('Source Talk Page never has been archived.')
            numbers = [0]
        numbers.sort()
        self.last_counter = numbers[-1]
        return f'{self.last_counter}'

    def set_min_thread_to_archive(self, min_threads_to_archive):
        if min_threads_to_archive:
            self.min_threads_to_archive = min_threads_to_archive

    def set_title_by_counter(self, prefix: str, archive: str) -> NoReturn:
        # archive = self.simplify_miszabot_params(archive)
        title = f'{archive}'.replace('~', prefix)
        self.title = title
        self.bared_title = title
        if '{counter}' in title:
            title = title.replace('{counter}', self.get_counter())
            self.title = title

    def set_title_by_time_params(self, thread: 'Thread'):
        if (thread.deprecated or thread.done) and thread.last_signature and self.has_time_param:
            self.title = self.title.replace('{year}', f'{thread.last_signature.year}')
            self.title = self.title.replace('{month}', f'{thread.last_signature.month:>02}')

    def set_title_changing_counter(self, counter):
        self.title = self.bared_title.replace('{counter}', counter)

    def set_title_by_last_counter(self):
        self.title = self.bared_title.replace('{counter}', f'{self.last_counter}')

    def set_title_incrementing_counter(self):
        self.inc_counter()
        self.title = self.bared_title.replace('{counter}', f'{self.last_counter}')


class SourceConfig:
    def __init__(self):
        self.title = ''
        self.algo: Optional[Algo] = None
        self.min_threads_left: int = 5

    def set_min_thread_left(self, min_threads_left):
        if min_threads_left:
            self.min_threads_left = min_threads_left

    def __repr__(self):
        return f'<SourceConfig title: "{self.title}" algo: {self.algo}>'


class Thread:
    """
    Classe que representa una secció d'una pàgina de discussió, o fil de discussió (thread).
    """

    def __init__(self):
        self.id = 0
        self.title: str = ''
        self.body: str = ''
        self.last_signature: Optional[datetime] = None
        self.elapsed_time: Optional[relativedelta] = None
        self.done: bool = False
        self.deprecated: bool = False
        self.source_for_rejected_thread: Optional[str] = None

    def __repr__(self):
        return f'<Thread id: {self.id}, t:"{self.title}", sz: {self.size} B, dt: {self.last_signature}, ' \
               f'{"deprecated" if self.deprecated else "done" if self.done else ""}>'

    @property
    def elapsed_time_str(self) -> str:
        et = self.elapsed_time
        to_str = ''
        if et:
            et_dict = {'y': et.years, 'm': et.months, 'd': et.days, 'h': et.hours, "'": et.minutes, '"': et.seconds}
            to_str = ' '.join(f'{v}{k}' for k, v in et_dict.items() if v > 0)
        return to_str

    @property
    def length(self) -> int:
        """Size counting codepoints (characters)."""
        return len(self.to_text())

    @property
    def size(self) -> int:
        """Size counting bits. This corresponds to MediaWiki's definition of page size."""
        return len(self.to_text().encode('utf-8'))

    def set(self, title, body) -> NoReturn:
        self.title = title
        self.body = body
        # TODO: la darrera signatura podria no ser la més recent?
        signatures = [
            utils.get_datetime(date_str) for date_str in utils.patterns.date.findall(self.body)
        ]
        if signatures:
            self.last_signature = signatures[-1]
            now = datetime.now()
            self.elapsed_time = relativedelta(now, self.last_signature)

    def set_deprecated(self, algo: Algo) -> NoReturn:
        """
        El archivebot original agafa el timedelta estàndard, ací anem a gastar el relative delta del dateutil.
        :param algo:
        :type algo: Algo
        :return:
        """
        if algo.function != 'old' or not self.last_signature:
            return None
        delay = relativedelta(**{utils.reldelta_keys[algo.unit]['en']: algo.value})
        expire = self.last_signature + delay
        self.deprecated = datetime.now() > expire

    def set_done(self, algo: Algo) -> NoReturn:
        if algo.function != 'done' or not self.last_signature:
            self.done = False
            return
        done = bool(utils.patterns.done.search(self.body))
        delay = relativedelta(**{utils.reldelta_keys[algo.unit]['en']: algo.value})
        expire = self.last_signature + delay
        self.done = done and datetime.now() > expire

    def set_source(self, title) -> 'Thread':
        self.source_for_rejected_thread = title
        return self

    def to_text(self) -> str:
        return f'== {self.title} =={self.body}'


class ArchiveConfig:
    """
    Classe per a la configuració de l'arxivament d'una pàgina de discussió.
    """

    def __init__(self):
        self.source = SourceConfig()
        self.target = TargetConfig()

    def __repr__(self):
        return f'<Config {self.source.title} algo: {self.source.algo}, ' \
               f'max_archive_size: {self.target.max_size}, min_threads_left: {self.source.min_threads_left}, ' \
               f'min_threads_to_archive: {self.target.min_threads_to_archive} ' \
               f'archive_header: {self.target.header}>'

    @staticmethod
    def set_algorithm(string) -> Algo:
        algo = Algo()
        algo.set(string)
        return algo

    @staticmethod
    def set_max_size(size) -> Size:
        max_size = Size()
        max_size.set(size)
        return max_size

    @staticmethod
    def check_values(cfg) -> NoReturn:
        for key, value in cfg.items():
            if value:
                if value.strip() == '-':
                    cfg[key] = None
                if value.isdigit():
                    cfg[key] = int(value)

    def set_by_dict(self, cfg) -> NoReturn:
        self.check_values(cfg)

        self.source.title = cfg['page']
        self.source.algo = self.set_algorithm(cfg['algo'])
        self.source.set_min_thread_left(cfg['minthreadsleft'])
        self.target.set_title_by_counter(cfg['page'], cfg['archive'])
        self.target.max_size = self.set_max_size(cfg['maxarchivesize'])
        self.target.set_min_thread_to_archive(cfg['minthreadstoarchive'])
        self.target.header = cfg['archiveheader']

    def simplify_miszabot_params(self, archive: str) -> NoReturn:
        """
        TODO: mirar si nom d'arxiu sense zero a l'esquerra, etc.
        TODO: Ara mateix monthname[short] no es tracta.
        TODO?: %(isoyear)d, %(isoweek)d, %(semester)d, %(quarter)d, %(week)d, %(localcounter)s, %(localyear)s,
        TODO?: %(localisoyear)s, %(localisoweek)s, %(localsemester)s, %(localquarter)s, %(localmonth)s, %(localweek)s
        Per defecte:
         -year = yyyy
         -month = mm
         -counter = c
        :param archive: str
        :return:
        """
        patterns = {
            # %(counter)d
            r'(%\(counter\)\d*d)': '{counter}',
            # %(year)d
            r'(%\(year\)\d*d)': '{year}',
            # %(month)d
            r'(%\(month\)\d*d)': '{month}',
            # %(monthname)s & $(monthnameshort)s
            r'(%\(monthname)(short)?(\)s)': '{monthname}'
        }
        for pattern in patterns:
            match = re.match(pattern, archive)
            if match:
                if len(match.groups()) == 1:
                    archive = re.sub(pattern, patterns[pattern], archive)
                elif len(match.groups()) == 3:
                    archive = re.sub(pattern, r'\1\2\3', archive)

        return archive


class TargetArchive:
    def __init__(self, config: TargetConfig):
        self.title = config.title
        self.page: Optional[ExtendedPage] = None
        self.config: TargetConfig = config
        self.threads: List[Thread] = []
        self.all_threads_size = 0
        self.set_page()

    def set_page(self) -> NoReturn:
        if not any(item in self.title for item in self.config.std_time_items):
            self.page = ExtendedPage(site, self.title)

    def set_all_threads_size(self) -> NoReturn:
        self.all_threads_size = sum(t.size for t in self.threads)

    def reset_title(self, title) -> NoReturn:
        self.title = title
        self.config.title = title

    def set_title_by_time_params(self, thread) -> NoReturn:
        self.config.set_title_by_time_params(thread)
        self.title = self.config.title

    def is_full(self) -> bool:
        page_is_full = False
        if self.config.max_size.unit == 'T':
            if self.page.threads == self.config.max_size.value:
                page_is_full = True
            return page_is_full

        size = self.config.max_size
        page_size = self.page.size
        if page_size > 0 and (page_size >= size.real_max_size or page_size >= size.to_int()):
            page_is_full = True
        return page_is_full

    def replace_title_incrementing_counter(self, summary) -> NoReturn:
        self.config.set_title_incrementing_counter()
        self.title = self.config.title
        self.page = ExtendedPage(site, self.config.title)
        self.page.header = self.config.header
        summary.add_target(self.title)

    def check_archiving(self, summary) -> NoReturn:
        """
        Hem de comprovar que podem arxivar tots els fils a la pàgina o cal crear-ne una altra.
        Dos casos possibles:
        - utilitzem un contador,
        - no utilitzem un contador, però la pàgina és plena. De moment no el tractem.
        """
        full = self.is_full()
        if not full:
            summary.add_target(self.title)
            summary.add_threads([t.title for t in self.threads])
            self.page.append_sections(self.threads, summary.insert_message)
        elif full and self.config.has_counter:
            self.replace_title_incrementing_counter(summary)
            threads_copy = list(self.threads)
            max_size = self.config.max_size.to_int()
            by_threads = self.config.max_size.to_int() < 0
            while threads_copy:
                left_threads = []
                for thread in threads_copy:
                    left_threads.append(thread)
                    threads_size = sum([t.size for t in left_threads])
                    if by_threads and len(left_threads) >= -max_size:
                        break
                    elif not by_threads and threads_size >= max_size:
                        break
                for thread in left_threads:
                    threads_copy.remove(thread)
                summary.add_threads([t.title for t in left_threads])
                self.page.append_sections(left_threads, summary.insert_message)
                if threads_copy:
                    self.replace_title_incrementing_counter(summary)
        else:
            raise NotImplementedError("No cap tanta cosa i no es tracta d'un arxivament amb contador...")


class SourceDiscussion:
    """
    Classe que contindrà elements que es puguen arxivar, però també aquells que per algun error no s'hagen pogut
    arxivar.
    """

    def __init__(self, config: SourceConfig):
        self.title = config.title
        self.page = ExtendedPage(site, config.title)
        self.config: SourceConfig = config
        self.threads: List[Thread] = []
        self.all_threads_size = 0

    def __repr__(self):
        return f'<ArchiveSource {self.title} {self.config} {self.threads}>'

    def set_all_threads_size(self) -> NoReturn:
        self.all_threads_size = sum(t.size for t in self.threads)

    def run(self) -> NoReturn:
        """
        Ací obtenim les seccions d'una pàgina de discussió
        :return:
        """
        content = self.page.text
        talks = utils.patterns.threads.split(content)[1:]
        done = 0
        for i in range(0, len(talks) - 1, 2):
            thread = Thread()
            thread.id = len(self.threads) + 1
            title = talks[i]
            body = talks[i + 1]
            thread.set(title.strip(), body)
            thread.set_done(self.config.algo)
            done += int(thread.done)
            thread.set_deprecated(self.config.algo)
            self.threads.append(thread)


class ExtendedPage(Page):
    """
    Extenc la classe Page, de moment per:
     - obtenir-ne la mida de la pàgina segons els criteris de Meta (en octets i no en caràcters).
     - eliminar seccions de la pàgina.
     - afegir contingut al final de la pàgina
     - TODO: ordenar fils per data
    """

    def __init__(self, page_site, page_title):
        Page.__init__(self, page_site, page_title)
        self.debug = globals().get('debug')
        self.header = ''
        self.inserting = 0

    @property
    def size(self) -> int:
        if not self.exists():
            return -1
        return len(self.text.encode('utf8'))

    @property
    def threads(self) -> int:
        return len(utils.patterns.threads.findall(self.text))

    def set_header(self, header) -> NoReturn:
        if header:
            self.header = f'{header}\n\n'

    def append(self, new_text, comment) -> NoReturn:
        old_text = self.text
        if self.size == -1:
            new_text = f'{self.header}{new_text}'
        new_text = f"{old_text}\n\n{new_text}"
        if self.debug:
            print(f'INSERTING: {self.title()} {len(new_text)} {self.inserting}')
        else:
            self.put(new_text, summary=comment)

    def append_sections(self, sections: List[Thread], summary) -> NoReturn:
        self.inserting = len(sections)
        new_text = ''
        for section in sections:
            new_text = f'{new_text}{section.to_text()}'
        self.append(new_text, summary)

    def remove_sections(self, sections: List[Thread], summary) -> NoReturn:
        old_text = self.text
        new_text = f'{old_text}'
        for section in sections:
            new_text = new_text.replace(section.to_text(), '')
        if len(new_text) < len(old_text):
            if self.debug:
                new = 'NEW PAGE!' if self.size == -1 else ''
                print(
                    f'REMOVING: {self.title()} old[{len(old_text)}] new[{len(new_text)}] '
                    f'diff[{len(old_text)-len(new_text)}]{new}')
            else:
                self.put(new_text, summary)

    def replace_template(self) -> NoReturn:
        content = self.text
        if 'Usuari:VriuBot/Arxivador' in content:
            content = content.replace('Usuari:VriuBot/Arxivador', 'Usuari:ArxivaBot/config')
            self.put(content, "Bot: modificant inclusió de la pàgina de configuració d'arxivament de discussió.")

    def remove_template(self, tpl, summary) -> NoReturn:
        content = self.text
        self.put(content.replace(f'{tpl}', ''), summary)

    def what_links_here(self, ns: Union[int, Tuple[int, ...]] = 3):
        """
        MediaWiki: Special:WhatLinksHere
        API: linkshere, backlinks
        pywikibot: getReferences <- page_embeddedin | pagebacklinks throw API:embeddedin | API:backlinks
        """
        return self.getReferences(only_template_inclusion=True, follow_redirects=False, namespaces=ns, content=False)


class ExtendedUser(User):
    def __init__(self, name):
        User.__init__(self, site, name)

    @property
    def is_inactive(self) -> bool:
        last_contrib = list(self.contributions(1))
        if last_contrib:
            edited_page, period, timestamp, summary = last_contrib[0]
            elapsed_time = relativedelta(timestamp.now(), timestamp)
            return elapsed_time.years >= 1 or elapsed_time.months > 3


class ArchiveCollector:
    """
    Classe que recol·lecta les pàgines amb discussions que s'han d'arxivar.
    A la pàgina del bot "Usuari:ArxivaBot/Arxivador" trobem una taula amb
    les pàgines i la seua configuració d'arxivament.
    """

    def __init__(self):
        self.page = Page(site, 'Usuari:ArxivaBot/Arxivador')
        self.pages: Iterable[Page] = []
        self.compat_pages: Iterable[Page] = []
        self.source_archives: List[SourceDiscussion] = []
        self.archiver: Dict[SourceDiscussion, Dict[TargetArchive, List[Thread]]] = {}
        self.rejected_list: List[Thread] = []

    def get_archiver(self, target) -> TargetArchive:
        for cur_source in self.archiver:
            for cur_target in self.archiver[cur_source]:
                if cur_target.title == target.title:
                    return cur_target
        return TargetArchive(target.config)

    def set_archiver(self, source: SourceDiscussion, config: TargetConfig) -> NoReturn:
        target = TargetArchive(config)
        parametrized_target_title = target.title
        for thread in source.threads:
            if thread.done or thread.deprecated:
                target.reset_title(parametrized_target_title)
                target.set_title_by_time_params(thread)
                tgt = self.get_archiver(target)
                if source not in self.archiver:
                    self.archiver[source] = {}
                if tgt not in self.archiver[source]:
                    self.archiver[source][tgt] = []
                self.archiver[source][tgt].append(thread)

    def load_table(self) -> NoReturn:
        """
        Ací obtenim les pàgines i la seua configuració
        """
        content = self.page.text
        for items in utils.patterns.table_row.finditer(content):
            group_dict = items.groupdict()
            # config
            config = ArchiveConfig()
            config.set_by_dict(group_dict)
            # source
            source = SourceDiscussion(config.source)
            self.fetch_threads(source)
            self.source_archives.append(source)
            self.set_archiver(source, config.target)

    @staticmethod
    def get_raw_template(page, tpl_name, user) -> str:
        raw_template = ''
        content = page.text
        pattern = re.compile(
            r'(\{\{\s*%(tpl)s\s*\|.*?(?:archiveheader\s*=\s*\{\{.*?\}\})?.*?\}\}\n*)' % {'tpl': tpl_name},
            re.DOTALL
        )
        match = pattern.search(content)
        if match:
            raw_template = match.group(1)
            user = ExtendedUser(user)
            if user.is_inactive:
                print(user.username, 'is inactive')
            if page.title(without_brackets=True).startswith('Usuari Discussió:ArxivaBot'):
                page = ExtendedPage(site, page.title(with_section=True, without_brackets=True))
                # page.remove_template(raw_template, f'Bot: supressió de plantilla per inactivitat de l'usuari durant {90} dies')
        return raw_template

    def fetch_config(self, iterator, tpl_name) -> List[Dict[str, str]]:
        """Obtenim configuració des de la invocació d'Usuari:ArxivaBot/config i semblants."""
        configs = []
        for page in iterator:
            templates = {pg.title(): params for pg, params in page.templatesWithParams()}
            tpl = templates.get(tpl_name)
            if tpl:
                config = dict(p.split('=', 1) for p in tpl)
                config['page'] = page.title(without_brackets=True, with_section=True)
                config['from'] = tpl_name.split(':')[1].split('/')[0]
                user = config['page'].split(':')[1].split('/')[0]
                raw_template = self.get_raw_template(page, tpl_name, user)
                config['raw_tpl'] = raw_template
                configs.append(config)
        return configs

    def load_inclusions(self):
        """
        De moment no l'utilitzem
        """
        title = 'Usuari:ArxivaBot/config'
        tmp_page = ExtendedPage(site, title)
        arxivabot_pages = tmp_page.what_links_here((3, 4))
        configs = self.fetch_config(arxivabot_pages, title)

        title = 'Usuari:VriuBot/Arxivador'
        tmp_page = ExtendedPage(site, title)
        vriubot_pages = tmp_page.what_links_here((3, 4))
        configs.extend(self.fetch_config(vriubot_pages, title))

        title = 'User:MiszaBot/config'
        tmp_page = ExtendedPage(site, title)
        miszabot_pages = tmp_page.what_links_here(3)
        self.fetch_config(miszabot_pages, title)

        print(configs)

    def fetch_threads(self, source: SourceDiscussion) -> NoReturn:
        if source.title.startswith('Viquipèdia:La taverna'):
            return
        source.run()

    def run(self):
        """
        Una vegada carreguem les pàgines i la configuració mitjançant el mètode load()
        analitzem els fils de discussió.
        """
        self.load_table()
        # self.load_inclusions()

    def show(self) -> NoReturn:
        self.load_table()
        for archiver in self.source_archives:
            print(f'{archiver.title} {len(archiver.threads)} {archiver.config}')
            done = deprecated = 0
            for thread in archiver.threads:
                done += int(thread.done)
                deprecated += 1 if thread.deprecated else 0
                handler = f'done: {thread.done}' \
                    if archiver.config.algo.function == 'done' else f'deprecated: {thread.deprecated}'
                print(f'\t{thread.id} {thread.title} {thread.last_signature} {thread.elapsed_time_str}  '
                      f'size: {thread.size} len: {thread.length} {handler}')
                if thread.done or thread.deprecated:
                    target = [
                        ta for ta in self.archiver[archiver]
                        for th in self.archiver[archiver][ta]
                        if th.title == thread.title
                    ]
                    print(f'\t\tarchive to: {target[0].title}')
            if archiver.config.algo.function == 'done':
                print(f"DONE: {done}/{len(archiver.threads)}")
            else:
                print(f"DEPRECATED: {deprecated}/{len(archiver.threads)}")

    def stats(self) -> NoReturn:
        self.load_table()
        for archiver in self.source_archives:
            done = deprecated = 0
            for thread in archiver.threads:
                done += int(thread.done)
                deprecated += 1 if thread.deprecated else 0
            print(archiver.title, len(archiver.threads), done, deprecated)
        print('\nTargets')
        for a in self.archiver:
            print(a.title, len(self.archiver[a].keys()),
                  len(list(_ for t in self.archiver[a] for _ in self.archiver[a][t])),
                  [t.config for t in self.archiver[a]])

    def go(self) -> NoReturn:
        """
        Ací ho fem tot.

        Hem de comprovar si les seccions a inserir compleixen els requisits.
        :return:
        """
        self.load_table()
        for source_talk in self.archiver:
            summary = Summary(source_talk.title)
            summary.algo = source_talk.config.algo
            removed = []
            leaving_threads = 0
            all_threads_in_source = len(source_talk.threads)
            for target_talk in self.archiver[source_talk]:
                # Omplim mentre no s'iguale el mínim de fils romaments de la configuració.
                threads = []
                wrong_threads = []
                for thread in self.archiver[source_talk][target_talk]:
                    if source_talk.config.min_threads_left <= all_threads_in_source - leaving_threads and \
                            '{year}' not in target_talk.title:
                        leaving_threads += 1
                        threads.append(thread)
                    elif '{year}' in target_talk.title:
                        wrong_threads.append(thread)
                if wrong_threads:
                    self.rejected_list.extend(wrong_threads)
                # No hem aplegat al mínim configurat, no hi ha suficients fils per a arxivar, es queden a la pàgina.
                if target_talk.config.min_threads_to_archive > len(threads):
                    print(f"{target_talk.title} no té prous fils per arxivar ({len(threads)})")
                    continue
                if threads:
                    removed.extend(threads)
                    target_talk.threads = threads
                    target_talk.set_all_threads_size()
                    target_talk.page.set_header(target_talk.config.header)
                    target_talk.check_archiving(summary)
            if removed:
                source_talk.page.remove_sections(removed, summary.remove_message)
        print('rejected', self.rejected_list)


if __name__ == '__main__':
    debug = False
    collector = ArchiveCollector()
    collector.go()

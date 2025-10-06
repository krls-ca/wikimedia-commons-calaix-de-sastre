#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
script original per KRLS
modificat el 14/03/2025 per Coet
"""

import argparse
import json
import os
import pickle
import re
import sys

import requests
import traceback

from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from random import randint
from string import Template
from time import sleep as wait
from typing import Dict, Iterator, List, Literal, Optional, Tuple
from urllib.parse import urlparse

from dateutil.relativedelta import relativedelta
from pywikibot import Category, FilePage, Page, Site
from pywikibot.exceptions import APIError, UploadError
from pywikibot.pagegenerators import SubCategoriesPageGenerator, CategorizedPageGenerator, PrefixingPageGenerator

Mode = Literal['full', 'light', 'resume']
Status = Literal['copyright', 'blacklisted', 'new', 'pending', 'uploaded']


class AlreadyUploadedException(Exception):
    def __init__(self, message="Previously uploaded file."):
        self.message = message
        super().__init__(self.message)


class DateTime:
    def __init__(self, source: datetime | date | str | int | float | None = None):
        self._source = source
        self.dt: Optional[datetime] = datetime.now()
        if source:
            self._dispatch()

    def __repr__(self):
        return f"<DateTime at {hex(id(self))}, dt={self.dt:%Y-%m-%d %H:%M:%S}>"

    def __format__(self, format_spec):
        modifier = '-' if sys.platform.startswith('lin') else '#'
        # Skipping heading zeros like PHP specifiers (j & n, but not h where PHP gets G)
        if '%h' in format_spec:
            format_spec = format_spec.replace('%h', f'%{modifier}H')
        if '%j' in format_spec:
            format_spec = format_spec.replace('%j', f'%{modifier}d')
        if '%n' in format_spec:
            format_spec = format_spec.replace('%n', f'%{modifier}m')
        return self.dt.__format__(format_spec)

    def _dispatch(self):
        match self._source:
            case str() if 'T' in self._source:
                self.from_api(self._source)
            case str() if 'T' not in self._source:
                self.from_date_str(self._source)
            case datetime():
                self.from_datetime(self._source)
            case date():
                self.from_date(self._source)
            case int():
                self.from_ordinal(self._source)
            case float():
                self.from_timestamp(self._source)
            case _:
                raise TypeError(f"Source type not supported: {type(self._source).__name__}")

    @property
    def year(self):
        if not self.dt:
            raise AttributeError("No date has been set.")
        return self.dt.year

    @property
    def month(self):
        if not self.dt:
            raise AttributeError("No date has been set.")
        return self.dt.month

    @property
    def day(self):
        if not self.dt:
            raise AttributeError("No date has been set.")
        return self.dt.day

    @property
    def hour(self):
        if not self.dt:
            raise AttributeError("No date has been set.")
        return self.dt.hour

    @property
    def minute(self):
        if not self.dt:
            raise AttributeError("No date has been set.")
        return self.dt.minute

    @property
    def second(self):
        if not self.dt:
            raise AttributeError("No date has been set.")
        return self.dt.second

    @property
    def millisecond(self):
        if not self.dt:
            raise AttributeError("No date has been set.")
        return self.dt.microsecond // 1000

    @property
    def microsecond(self):
        if not self.dt:
            raise AttributeError("No date has been set.")
        return self.dt.microsecond

    @property
    def weekday(self):
        if not self.dt:
            raise AttributeError("No date has been set.")
        # human POV, 1 for Monday, 7 for Sunday
        return self.dt.weekday() + 1

    def from_date_str(self, source: str):
        """from string with %d-%m-%Y or %d/%m/%Y"""
        sep = '-' if '-' in source else '/'
        self.dt = datetime.strptime(source, f"%d{sep}%m{sep}%Y")
        return self

    def from_datetime_str(self, source: str):
        """from string with %d-%m-%Y, %H:%M[:%S] or %d/%m/%Y, %H:%M[:%S]"""
        source = source.replace('/', '-')
        if source.count(':') == 2:
            self.dt = datetime.strptime(source, f"%d-%m-%Y, %H:%M:%S")
        elif source.count(':') == 1:
            self.dt = datetime.strptime(source, f"%d-%m-%Y, %H:%M")
        return self

    def from_api(self, source: str):
        self.dt = datetime.strptime(source, "%Y-%m-%dT%H:%M:%S.%f")
        return self

    def from_ordinal(self, source: int):
        self.dt = datetime.fromordinal(source)

    def from_timestamp(self, source: float):
        self.dt = datetime.fromtimestamp(source)

    def from_api_timestamp(self, source: int):
        self.dt = datetime.fromtimestamp(source/1000)

    def from_datetime(self, source: datetime):
        self.dt = source
        return self

    def from_date(self, source: date):
        self.dt = datetime(source.year, source.month, source.day)
        return self

    def to_timestamp(self):
        return self.dt.timestamp()

    def to_api_timestamp(self):
        return int(self.to_timestamp()*1000)

    def to_ordinal(self):
        return self.dt.toordinal()

    def to_date(self):
        return self.dt.date()

    def to_datetime(self, max_time=False):
        if max_time:
            self.dt = self.dt.combine(self.dt.date(), time.max)
        return self.dt

    def to_iso_format(self, max_time=False):
        if max_time:
            self.dt = self.dt.combine(self.dt.date(), time.max)
        return self.dt.isoformat(timespec='milliseconds')


@dataclass
class GenCatImage:
    id: str
    title: str
    subtitle: str
    download_url: str
    extension: str
    publication_date: str  # Date
    agency: list
    cat_image: int
    timestamp: int
    status: Status = 'new'
    width: int = None
    height: int = None

    @property
    def source(self):
        return f"https://govern.cat/salapremsa/audiovisual/imatge/{self.cat_image}/{self.id}"


@dataclass
class CommonsImage:
    id: str
    filename: str
    subcategory: str
    source: str


class ImageIdLoader:
    """
    Classe per a obtenir llistes d'identificadors d'imatges de la Sala de Premsa Gen Cat:
        - uploaded_list: imatges pujades
        - copyright_list: imatges amb drets d'autor confirmades
        - pending_list: imatges potencialment amb drets d'autor (la llista conté id i url)
        - blacklist: ids d'imatges a descartar, la llista és manual.
    Estes llistes es pengen a Commons per centralitzar, visualitzant i permetent la manipulació per qualsevol.
    """

    def __init__(self):
        self._attributes = ('uploaded', 'copyvio', 'pending', 'blacklist')
        self._uploaded_list = []
        self._copyright_list = []
        self._pending_list = []
        self._blacklist = []
        self._stats = {_: 0 for _ in self._attributes}
        self.summary = Template('Bot, updating ids. Size: ${count} (${diff}).')
        self.host_page = 'User:CobainBot/GenCatImages/'

    @property
    def blacklist(self):
        return self._blacklist

    @property
    def copyright_list(self):
        return self._copyright_list

    def load(self):
        for subpage in self._attributes:
            page = Page(commons, f'{self.host_page}{subpage}')
            if page.exists():
                ids = re.findall(r'\d+', page.text)
                print(f"Attr. {subpage} loaded: {len(ids)} items.")
                if subpage == 'uploaded':
                    self._uploaded_list = ids
                elif subpage == 'pending':
                    self._pending_list = ids
                elif subpage == 'copyvio':
                    self._copyright_list = ids
                elif subpage == 'blacklist':
                    self._blacklist = ids
                self._stats[subpage] = len(ids)  # Retenim la talla inicial de la llista

    def fix_uploaded(self):
        self._uploaded_list = sorted(set(self._uploaded_list))

    def update_uploaded_ids(self, uploaded_ids):
        new_ids = set(uploaded_ids).difference(self._uploaded_list)
        self._uploaded_list.extend(new_ids)

    def add_pending_id(self, img_id):
        if img_id not in self._pending_list:
            self._pending_list.append(img_id)

    def _put(self, target: list[str], subpage: str):
        size = len(target)
        if self._stats[subpage] != size:
            page = Page(commons, f'{self.host_page}{subpage}')
            old_size = 0
            if old_comment := re.search(r'Size: (?P<size>\d+)', page.latest_revision.comment):
                old_size = int(old_comment.group('size'))
            diff = f'{size - old_size:+}'

            content = '\n'.join(target)
            page.put(content, self.summary.substitute(count=size, diff=diff), bot=True)

    def update(self):
        for subpage in self._attributes:
            if subpage == 'uploaded':
                self._put(self._uploaded_list, subpage)
            elif subpage == 'pending':
                self._put(self._pending_list, subpage)
            elif subpage == 'copyvio':
                self._put(self._copyright_list, subpage)
            elif subpage == 'blacklist':
                self._put(self._blacklist, subpage)


class ApiRequestBody:
    # noinspection SpellCheckingInspection
    def __init__(self, field='dataPublicacioPortal'):
        self.field = field
        self.start = ''
        self.end = ''
        self.after = None

    def set(self, start, end, after=None):
        self.start = DateTime(start).to_iso_format()
        self.end = DateTime(end).to_iso_format(max_time=True)
        self.after = after
        return self

    def __str__(self):
        return json.dumps(self.json)

    @property
    def json(self):
        request = {
            'sort': {self.field: {'order': 'asc'}}, 'query': {'bool': {'must': [{'range': {
                self.field: {'format': 'date_optional_time', 'gte': self.start, 'lte': self.end}}}],
                'filter': [{'match': {'type.main': '5'}}]}}
        }
        if self.after:
            request['search_after'] = [self.after]
        return request


class PremsaGenCatImageCollector:
    """
    Classe per a obtenir un json de la Premsa Gen Cat amb les dades d'imatges per pujar a Commons.

    Les dades obtingudes s'alcen en un fitxer binari que conté un històric de tot el que hem descarregat.
    Per defecte treballem sense carregar el fitxer.

    Els objectes recollits tenen quatre estats: uploaded, copyvio, pending, blacklist.

    En mode "resume" pujarem les imatges que s'hagen quedat en cua.
    El "light" no carrega el fitxer binari, només les imatges que s'obtenen de l'API. És el mode per defecte.
    El mode "full" carrega el fitxer binari que conté totes les dades sobre les imatges incloent l'estat en que es
    troben. Este mode s'abandonarà quan Commons estarà al dia.

    Nota: per a una pujada efectiva és millor carregar dades d'un sol dia, de manera que s'obté totes les imatges,
    carregar diversos dies fa que l'API no responga amb totes les imatges.

    :param size: número d'items a agafar de l'API
    :param mode: Mode, hi ha tres modes: light, full i resume. Light és el mode per defecte.
    """

    def __init__(self, size=250, mode: Mode = 'light'):
        self._mode: Mode = mode
        self.last_element: Optional[GenCatImage] = None
        self._response: Optional[Dict] = None
        self._image_dict: Optional[Dict] = None  # Depends on response
        self._api_url = "https://cercadorgovern.extranet.gencat.cat/documents-ca//_search?" \
                        f"size={size}&track_total_hits=true&filter_path=hits.hits._source,hits.hits.sort,hits.total"
        self._request_body = ApiRequestBody()

        self._null_pattern = re.compile(r' null$')
        self.batch: Dict[str, GenCatImage] = {}
        self._batch_file = Path('../resources/gen_cat_batch.bin')

    @property
    def total(self) -> Optional[int]:
        if not self._response:
            return None
        return self._response['total']['value']

    @property
    def size(self) -> int:
        if not self._image_dict:
            return 0
        return len(self._image_dict)

    def _request(self) -> dict:
        wait(randint(3, 10))
        after = self.last_element.timestamp if self.last_element else None
        query = self._request_body.set(args.start_date, args.end_date, after)
        response = requests.post(self._api_url, json=query.json, timeout=40)
        if response.status_code != 200:
            raise Exception(f"Status Code {response.status_code}")
        return response.json()

    def _fetch(self) -> bool:
        response: dict = self._request()
        if 'hits' in response and 'hits' in response['hits']:
            # Tenim imatges
            self._response = response['hits']
            self._image_dict = response['hits']['hits']
            print(f"fetched {len(self._image_dict)}")
            return True
        elif 'hits' in response and 'hits' not in response['hits']:
            # Ja no en queden
            self._response = response['hits']
            self._image_dict = []
            return False
        return False

    def _clean_null(self, source: dict[str, str]):
        content = source['subtitol']
        return self._null_pattern.sub('', content)

    @staticmethod
    def _get_file_extension(url: str) -> str:
        return os.path.splitext(urlparse(url).path)[1]

    # noinspection SpellCheckingInspection
    def _get_multimedia_info(self, source: dict[str, dict[str, str]]) -> Tuple[int, int, str, str]:
        multimedia = source['multimedia']
        height: int | None = multimedia.get('alcada')
        width: int | None = multimedia.get('amplada')
        url: str = multimedia.get('downloadUrl')
        ext: str = self._get_file_extension(url)
        return height, width, ext, url

    @staticmethod
    def _parse_agencies(source: dict[str, list[dict[str, str]]]):
        departments = source['departaments']
        return [depart['abreviatura'] for depart in departments]

    def _set_image(self, element: dict):
        source = element['_source']
        height, width, extension, url = self._get_multimedia_info(source)
        return GenCatImage(
            id=source['sourceId'],
            title=source['titular'],
            subtitle=self._clean_null(source),
            download_url=url,
            extension=extension,
            publication_date=source['dataPublicacioPortal'],
            cat_image=source['type']['subtype'],  # confirma que ok
            agency=self._parse_agencies(source),
            timestamp=element['sort'][0],
            height=height,
            width=width
        )

    @staticmethod
    def between_dates(img_list: List[GenCatImage]) -> Iterator[GenCatImage]:
        start = DateTime(args.start_date).to_ordinal()
        end = DateTime(args.end_date).to_ordinal()
        for img in img_list:
            img_timestamp = DateTime(img.publication_date).to_ordinal()
            if end >= img_timestamp >= start:
                yield img

    def get_new_images(self) -> Iterator[GenCatImage]:
        if self._mode in ('light', 'resume'):
            return (img for img in self.batch.values() if img.status == 'new')
        if args.start_date and args.end_date:
            return self.between_dates([img for img in self.batch.values() if img.status == 'new'])
        return (img for img in self.batch.values() if img.status == 'new')

    def find_all(self, untouched_ids: List[str]):
        self._load()
        self.batch = {img.id: img for img in self.batch.values() if img.id in untouched_ids}

    def set_mode(self, mode: Mode):
        self._mode = mode

    def run(self):
        # Tenim carregades les imatges que es van quedar sense processar, no extraem més dades.
        if self._mode == 'resume':
            return
        self.load()
        self._fetch()
        print(f"Processing {self.total} of images ...")
        processed = 0
        while self.size > 0:
            for image_data in self._image_dict:
                image = self._set_image(image_data)
                self.batch[image.id] = image
                self.last_element = image
                processed += 1
            self.save()
            print(f"Processed images: {processed} of {self.total}")
            if not self._fetch():
                break
        if processed != self.total:
            print(f"Process finished, processed: only {processed}, total: {self.total}")

    def load(self):
        if self._mode in ('light', 'resume'):
            return
        self._load()

    def _load(self):
        try:
            with open(self._batch_file, 'rb') as fp:
                self.batch = pickle.load(fp)
        except FileNotFoundError:
            self.batch = {}

    def _save(self):
        with open(self._batch_file, 'wb') as fp:
            # noinspection PyTypeChecker
            pickle.dump(self.batch, fp, pickle.HIGHEST_PROTOCOL)
            print('gen_cat_mgr.bin saved successfully.')

    def save(self):
        if self._mode in ('light', 'resume'):
            recent = self.batch
            collected = len(self.batch)
            self._load()
            old_size = len(self.batch)
            self.batch.update(recent)
            new_size = len(self.batch)
            inserted = new_size - old_size
            print(f'collected: {collected}, inserted: {inserted}')
            self._save()
            self.batch = recent
        else:
            self._save()

    def update(self):
        temp_batch = self.batch
        self._load()
        self.batch.update(temp_batch)
        self._save()


class UploadManager:
    """
    Amb esta classe controlem si un identificador d'una imatge s'ha pujat a Commons, només determinem si ha acabat
    allí o s'ha quedat en cua.
    """

    def __init__(self):
        self._filename = Path('../resources/gen_cat_mgr.bin')
        self.start_datetime: Optional[datetime] = None
        self.end_datetime: Optional[datetime] = None
        self.uploaded_ids: List[str] = []
        self.rejected_ids: List[str] = []
        self._id_queue: List[str] = []

    def queue_has_items(self):
        self._load()
        if self._id_queue:
            print(f"Queue has {len(self._id_queue)} items. Last running: {self.start_datetime:%d-%m-%Y %H:%M:%S}")
            print(f"Last uploaded ids ({len(self.uploaded_ids)}): {self.uploaded_ids}")
            return True
        self._reset()
        return False

    def add_uploaded(self, img_id):
        self.uploaded_ids.append(img_id)
        if img_id in self._id_queue:
            self._id_queue.remove(img_id)
        self._save()

    def add_rejected(self, img_id):
        print(f"adding existing id: {img_id}")
        self.rejected_ids.append(img_id)
        if img_id in self._id_queue:
            self._id_queue.remove(img_id)
        self._save()

    def reveal(self) -> List[str]:
        print(f"processed: {len(self.uploaded_ids) + len(self.rejected_ids)}, uploaded: {len(self.uploaded_ids)}, "
              f"rejected: {len(self.rejected_ids)}")
        return self.uploaded_ids + self.rejected_ids

    def resume(self):
        return self._id_queue

    def _reset(self):
        self.start_datetime: Optional[datetime] = datetime.now()
        self.end_datetime: Optional[datetime] = None
        self.uploaded_ids: List[str] = []
        self.rejected_ids: List[str] = []
        self._id_queue: List[str] = []

    def _load(self):
        try:
            with open(self._filename, 'rb') as fp:
                this: UploadManager = pickle.load(fp)
                self.start_datetime = this.start_datetime
                self.end_datetime = this.end_datetime
                self.uploaded_ids = this.uploaded_ids
                self.rejected_ids = this.rejected_ids
                self._id_queue = this._id_queue
        except FileNotFoundError:
            pass

    def _save(self):
        with open(self._filename, 'wb') as fp:
            # noinspection PyTypeChecker
            pickle.dump(self, fp, pickle.HIGHEST_PROTOCOL)

    def update_id_queue(self, img_list: List[str]):
        img_set = set(img_list).difference(self._id_queue)
        self._id_queue.extend(img_set)
        self._save()

    def close(self):
        self.end_datetime = datetime.now()
        self._save()


class PremsaGenCatImageUploader:
    """
    Classe principal per pujar imatges a Commons.

    Carreguem:
     - ids d'imatges pujades (uploaded)
     - ids d'imatges amb drets d'autors (copyvios)
     - ids d'imatges sospitoses de tindre drets d'autors (pending) i s'han de validar (allowed)
     - ids que no es consideren vàlides per a pujar (blacklist).

     NOTA: el parèntesi correspon a la subpàgina: [[commons:User:CobainBot/GenCatImages/<parentesi>]]

     S'inicia el procés d'extracció de dades de l'API de Premsa Gen Cat amb el PremsaGenCatCollector
     que mantenim en una llista (batch).
     Es carreguen les ids descrites més amunt. Amb UploaderManager gestionem les pujades per a poder restablir
     reprenent des d'on s'havia quedat en cas de desconnexió amb Commons.
     Iterem cada objecte de GenCatImage del lot (batch), creem el contingut amb la plantilla i un nom de fitxer.
     Aleshores mirem que el fitxer no estiga ja en Commons. Amb tot això el pugem.
     Si tot va bé, amb ajuda del UploaderManager publicarem la llista d'ids pujades o establertes com a possibles
     copyvios.

     NOTA: A la imatge pujada a commons hi consta l'identificador de l'API en el camp de la plantilla
     Information anomenat source.
    """

    def __init__(self):
        self._known_ids = ImageIdLoader()
        self._collector = PremsaGenCatImageCollector()
        self._pattern = re.compile(r'^[. ]*(?P<word>foto(?:grafia)?|imat?ge)?[. ]*(?P<number>\d+)?[. ]*$', re.I)
        # noinspection SpellCheckingInspection
        self._page_file_content = Template('''
== {{int:filedesc}} ==

{{Information
 |description    = {{ca|$title}}
 |date           = $date
 |source         = [$source $subtitle] (press release)
 |author         = $author
 |permission     = $permission
 |other versions =
 |other_fields 1 = {{InFi|Government agency|$agency}}
}}

[[Category:Images from Generalitat de Catalunya Press Room in $datecat]]
    ''')
        self._max_bytes = 218
        self._ugly_chars = str.maketrans('', '', '#<>[]|:/{}\n')
        self._disallowed_subjects = ("Obra d", "Peça d", "Imatge de '", "Cartells d", "Obres traduïdes al")
        self._manager: Optional[UploadManager] = None

    def __enter__(self):
        self._manager = UploadManager()
        self._load_untouched()
        return self

    def __exit__(self, *_):
        self._manager.close()
        self._known_ids.update_uploaded_ids(self._manager.reveal())
        self._known_ids.update()
        self._collector.update()  # actualitzar status

    def main(self):
        self._known_ids.load()
        self._dispatch()

    def _update_registers(self, img, success=True):
        img.status = 'uploaded'
        self._manager.add_uploaded(img.id) if success else self._manager.add_rejected(img.id)

    def _dispatch(self):
        self._collector.run()
        new_images = [img for img in self._collector.get_new_images()]
        self._manager.update_id_queue([img.id for img in new_images])
        for img in new_images:
            try:
                if self._check_image(img):
                    filename = self._sanitize(img)
                    content = self._set_template(img)
                    self._upload_image(img, filename, content)
            except AlreadyUploadedException as e:
                self._update_registers(img, False)
                print(e)

    def _load_untouched(self):
        if self._manager.queue_has_items():
            untouched = self._manager.resume()
            self._collector.find_all(untouched)
            self._collector.set_mode('resume')

    def _check_image(self, img: GenCatImage) -> bool:
        if img.id in self._known_ids.blacklist or img.id in self._known_ids.copyright_list:
            return False
        if any([img.title.startswith(subject) for subject in self._disallowed_subjects]):
            self._known_ids.add_pending_id(img.id)
            img.status = 'pending'
            return False
        return True

    def _add_context(self, filename: str) -> str:
        if match := self._pattern.search(filename):
            word = match.group('word').title() if match.group('word') else ''
            number = match.group('number').title() if match.group('number') else ''
            if word and number:
                expr = f'{word.title()} {number}'
            else:
                expr = word.title() if word else number
            filename = f"Generalitat de Catalunya Press Room - {expr}"
        return filename

    def _file_page_exists(self, filename: str, img_id: str):
        page = FilePage(commons, f"File:{filename}")
        if page.exists() and img_id in page.get():
            self._manager.add_rejected(img_id)
            raise AlreadyUploadedException(f"ContentId {img_id} already uploaded with filename: {filename}")

    def _remove_not_allowed_characters(self, filename: str) -> str:
        return filename.translate(self._ugly_chars)

    def _trunc_filename(self, filename: str) -> str:
        return (filename.encode('utf-8')[:self._max_bytes].decode('utf-8') + "...") \
            if len(filename.encode('utf-8')) > self._max_bytes else filename

    @staticmethod
    def _append_date(filename: str, img: GenCatImage) -> str:
        dt = DateTime(img.publication_date)
        return f'{filename} ({dt:%d-%m-%Y})'

    @staticmethod
    def _set_unique_filename(filename: str):
        filenames_in_use = len(list(PrefixingPageGenerator(filename, namespace='File', site=commons)))
        if filenames_in_use > 0:
            filename += f' - {filenames_in_use}'
        return filename

    def _sanitize(self, img: GenCatImage) -> str:
        filename = img.title
        filename = self._remove_not_allowed_characters(filename)
        filename = self._add_context(filename)
        filename = self._trunc_filename(filename)
        filename = self._append_date(filename, img)
        self._file_page_exists(f"{filename}{img.extension}", img.id)
        filename = self._set_unique_filename(filename)
        filename = f"{filename}{img.extension.lower()}"
        return filename

    def _set_template(self, img: GenCatImage) -> str:
        publ_date = DateTime(img.publication_date).to_datetime()
        date_cat = f'{publ_date:%B} {publ_date.year}' if publ_date.year > 2021 else publ_date.year
        return self._page_file_content.substitute(title=img.title,
                                                  date=f'{{{{Published on|{publ_date.date()}}}}}',
                                                  author='{{Institution:Govern de Catalunya}}',
                                                  permission='{{Attribution-govern}}',
                                                  subtitle=img.subtitle,
                                                  agency="/".join(img.agency),
                                                  source=img.source,
                                                  datecat=date_cat)

    def _upload(self, img: GenCatImage, filename: str, content: str):
        file_page = FilePage(commons, f"File:{filename}")
        file_page.upload(img.download_url, text=content,
                         comment="Uploading Generalitat de Catalunya Press Room image",
                         ignore_warnings=False, report_success=True)
        self._update_registers(img)

    def _upload_image(self, img: GenCatImage, filename: str, content: str):
        if args.debug:
            return
        try:
            self._upload(img, filename, content)
        except UploadError:
            self._update_registers(img, False)
            print(f"ContentId {img.id} already uploaded with filename: {filename}")
        except APIError as e:
            if "verification-error" in e.code:
                details = e.other['details']
                if details[0] == 'filetype-mime-mismatch':
                    new_extension = details[2]
                    match = re.match(r'image/(.*?)$', new_extension)
                    if match:
                        img.extension = f".{match.group(1)}"
                    else:
                        img.extension = f".{details[2]}"
                    print(f"Fixing verification-error: {filename}")
                    self._upload_image(img, filename, content)
            elif "duplicate" in e.code:
                self._update_registers(img, False)
                print(f"ContentId {img.id} already uploaded with filename: {filename}")
            elif "exists-normalized" in e.code:
                img.title = f"GENCAT - {img.title} ({img.id})"
                print(f"Fixing exists-normalized: {filename}")
                self._upload_image(img, filename, content)
            else:
                traceback.print_exc()
                for attr in (e.args, e.info, e.other, e.code):
                    print(attr)
                print("S'ha produït un error inesperat.")
        except Exception:
            traceback.print_exc()
            print("Exception: s'ha produït un error inesperat.")


class CommonsCollector:
    """
    Esta classe ha sigut necessària per recòrrer totes les categories de [[commons:Category:Images from Generalitat de
    Catalunya Press Room]] en un esforç per recopilar totes les ids que ja s'havien pujat a Commons a 18/4/2025.
    """

    def __init__(self):
        self.category = Category(commons, "Images from Generalitat de Catalunya Press Room")
        self.images: Dict[str, CommonsImage] = {}
        self.file = Path('../resources/commons_files.bin')
        self.source_pattern = re.compile(r"https://govern\.cat/salapremsa/audiovisual/imatge/\d+/(?P<id>\d+)")

    def parse_template(self, file_page: FilePage) -> Tuple[str, str, str]:
        templates = file_page.raw_extracted_templates
        img_id = ''
        source = ''
        subtitle = ''
        for template in templates:
            title, order_dict = template
            if title != 'Information':
                continue
            source = order_dict.get('source', '')
            subtitle = order_dict.get('subtitle', '')
            match = self.source_pattern.search(source)
            if match:
                img_id = match.group('id')
        return img_id, source, subtitle

    def get_all_files(self, save=False):
        """
        Obtenim totes les imatges pujades a Commons

        Este mètode només ens és útil per recopilar totes les imatges que algú ha pujat per tindre un fitxer de totes
        les imatges pujades anteriorment al 18 de març 2025 a la categoria "Category:Images from Generalitat de
        Catalunya Press Room" i les seues subcategories. Ja que no hi ha un regsitre complet de totes les pujades.

        :param save: si volem alçar els resultats.
        :return:
        """
        file_gen = CategorizedPageGenerator(self.category)
        self._dispatch(file_gen)

        for subcategory in SubCategoriesPageGenerator(self.category, recurse=3):
            file_gen = CategorizedPageGenerator(subcategory, namespaces=6, recurse=False)
            self._dispatch(file_gen)

        if save:
            self.save()

    def _dispatch(self, file_gen):
        for file_page in file_gen:
            if not file_page.exists():
                continue

            img_id, source, subtitle = self.parse_template(file_page)
            if source and subtitle:
                self.images[img_id] = CommonsImage(img_id, file_page.title(), self.category.title(), source)
                print(f"[{datetime.now():%H:%M:%S}] images: {len(self.images)}")

    def load(self):
        with open(self.file, 'rb') as fp:
            self.images = pickle.load(fp)

    def save(self):
        with open(self.file, 'wb') as fp:
            # noinspection PyTypeChecker
            pickle.dump(self.images, fp, pickle.HIGHEST_PROTOCOL)

    def put(self, content):
        page = Page(commons, 'User:CobainBot/GenCatImages/uploaded')
        page.put(content, 'Bot: list of uploaded images ids', bot=True)


if __name__ == '__main__':
    commons = Site('commons', 'commons', 'CobainBot')
    parser = argparse.ArgumentParser(description="Exemple d'ús PremsaGencat.")
    parser.add_argument("--debug", action="store_true", help="No es pengen les imatges a Commons.")
    parser.add_argument("--date", dest="date", action="store",
                        help='Data en la qual vols importar. Per exemple, "01-01-2023"')
    parser.add_argument("--start", dest="start_date", action="store",
                        help='Data des de la qual vols importar. Per exemple, "01-01-2023"')
    parser.add_argument("--end", dest="end_date", action="store",
                        help='Data fins la qual vols importar, data inclusiva. Per exemple, "31-12-2023"')
    args = parser.parse_args()
    parser.print_help()

    if args.date and not (args.start_date and args.end_date):
        args.start_date = args.end_date = args.date
        del args.date
    elif args.date and (args.start_date or args.end_date):
        parser.error("--date no es pot emprar amb --start o --end")
    elif not args.date and not (args.start_date and args.end_date):
        parser.error("Indiqueu una data amb --date o un rang de dates amb --start i --end")

    with PremsaGenCatImageUploader() as premsa_gen_cat:
        premsa_gen_cat.main()

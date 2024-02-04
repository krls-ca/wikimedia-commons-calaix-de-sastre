#!/usr/bin/python
# -*- coding: utf-8 -*-

from datetime import datetime
import argparse
import os
import json
import re
import time
import sys
import traceback
from urllib.parse import urlparse
from random import randint
from string import Template
from paprika import data
#from scripts import upload
import requests
import pywikibot


class AlreadyUploadedException(Exception):
    def __init__(self, message="Previously uploaded file."):
        self.message = message
        super().__init__(self.message)
@data
class GencatImage:
    id: str
    title: str
    subtitle: str
    downloadUrl: str
    extension: str
    publicationDate: str #Date
    agency: list
    width: str
    catImage: str
    height: str

    def get_source(self):
        return f"https://govern.cat/salapremsa/audiovisual/imatge/{self.catImage}/{self.id}"

GENCAT_API_URL = "https://cercadorgovern.extranet.gencat.cat/documents-ca//_search?size=250&track_total_hits=true&filter_path=hits.hits._source,hits.hits.sort,hits.total"
GENCAT_API_QUERY = Template('{"sort":{"dataPublicacioPortal":{"order":"desc"}}, \
    "query":{"bool":{"must":[{"range":{"dataPublicacioPortal": \
    {"format":"date_optional_time","gte":"${start}","lt":"${end}"}}}], \
    "filter":[{"match":{"type.main":"5"}}],"must_not":[]}}${after}}')
UPLOAD_PAGE = Template('''
== {{int:filedesc}} ==

{{Information
 |description    = {{ca|${title}}}
 |date           = ${date}
 |source         = [${source} ${subtitle}] (press release)
 |author         = ${author}
 |permission     = ${permission}
 |other versions =
 |other_fields 1 = {{InFi|Government agency|${agency}}}
}}

[[Category:Images from Generalitat de Catalunya Press Room in ${datecat}]]
    ''')
MAX_BYTES = 218

def help():
    parser = argparse.ArgumentParser(description="Exemple d'ús PremsaGencat.")
    parser.add_argument("--debug", action="store_true", help="No es pengen les imatges a Commons.")
    parser.add_argument("--start", dest="start_date", action="store", \
        help="Data des del qual vols importar. Per exemple, 2023-10-12", required=True)
    parser.add_argument("--end", dest="end_date", action="store", \
        help="Data fins qual vols importar (dia no inclòs). Per exemple, 2023-10-13", required=True)
    parser.add_argument("--blacklist", action="store_true", \
        help="Genera una blacklist local que exclou els identificadors \
        d'imatges afegits. També afegeix a la blacklist aquelles imatges \
        que ja han estat carregades a Commons prèviament.")
    args = parser.parse_args()
    parser.print_help()
    return args

args = help()

if args.blacklist:
    try:
        file = open('premsaGencat_ids.txt', 'a+', encoding='utf8')
        copyrighted_images = open('copyright_violation.txt', 'a+', encoding='utf8')
    except (OSError, IOError) as e:
        print('Problemes per obrir l\'arxiu')
        sys.exit(0)

def strdatetime_to_date(strdatetime):
    return datetime.strptime(strdatetime, "%Y-%m-%dT%H:%M:%S.%f")

def strdate_to_datetime_utc(strdate):
    date = datetime.strptime(strdate, "%d-%m-%Y")
    custom_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    return date.strftime(custom_format)

def parse_agencies(departments):
    return [depart['abreviatura'] for depart in departments]

def clean_null(content):
    return ' '.join(content.rsplit(' null', 1)).strip()

def parse_content_information(element):
    #element['_source']['departaments']
    return GencatImage(
        id=element['_source']['sourceId'],
        title=element['_source']['titular'],
        subtitle=clean_null(element['_source']['subtitol']),
        downloadUrl=element['_source']['multimedia']['downloadUrl'],
        extension=get_file_extension(element['_source']['multimedia']['downloadUrl']),
        publicationDate=element['_source']['dataPublicacioPortal'],
        catImage=element['_source']['type']['subtype'], #confirma que ok
        agency=parse_agencies(element['_source']['departaments'])
        )

def remove_not_allowed_characters(filename):
    characters_to_remove = "#<>[]|:/{}"
    return filename.replace("\n", "").translate(str.maketrans('', '', characters_to_remove))

def is_blacklisted(filename):
    pattern = r'[fF][oO][tT][oO].?\d{1,2}\s*|[fF][oO][tT][oO]$|\.$| $|^\d+$| \.$'
    return re.fullmatch(pattern, filename)

def trunc_filename(filename):
    return (filename.encode('utf-8')[:MAX_BYTES].decode('utf-8') + "...") \
        if len(filename.encode('utf-8')) > MAX_BYTES else filename

def get_file_extension(url):
    return os.path.splitext(urlparse(url).path)[1]

def filename_already_exists(site, filename, idt):
    page = pywikibot.FilePage(site, f"File:{filename}")
    if page.exists() and idt in page.get():
        if args.blacklist:
            print(idt)
            file.write(f'{idt}\n')
        raise AlreadyUploadedException(f"ContentId {idt} already uploaded with filename: {filename}")
    return page.exists()

def parse_filename(filename):
    parsed_file = remove_not_allowed_characters(filename)
    if is_blacklisted(parsed_file):
        parsed_file = "Generalitat de Catalunya Press Room - " + parsed_file
    return trunc_filename(parsed_file)

def get_filename(site, content):
    filename_title = parse_filename(content.title)
    print(filename_title)
    date = strdatetime_to_date(content.publicationDate).strftime("%d-%m-%Y")
    filename = f'{filename_title} ({date}){content.extension}'
    print(filename)
    if not filename_already_exists(site, filename, content.id):
        return filename

    for i in range(10):
        filename = f'{filename_title} ({date}) - {i}{content.extension}'
        if not filename_already_exists(site, filename, content.id):
            return filename

    print("NO HAURÍEM D'ARRIBAR AQUÍ")
    sys.exit(0)

def upload(site, content, filename, upload_content):
    print(upload_content)
    file_page = pywikibot.FilePage(site, f"File:{filename}")
    file_page.upload(content.downloadUrl, text=upload_content, comment="Uploading Generalitat de Catalunya Press Room image", \
     ignore_warnings=False, report_success=True)

def upload_image(site, content):
    date = strdatetime_to_date(content.publicationDate)
    upload_content = UPLOAD_PAGE.substitute(title = content.title, #
        date=f'{{{{Published on|{date.date()}}}}}', #
        author='{{Institution:Govern de Catalunya}}', #
        permission='{{Attribution-govern}}', #
        subtitle = content.subtitle, #
        agency = "/".join(content.agency), #
        source=content.get_source(), #
        datecat=f'{date.strftime("%B")} {date.year}' if date.year > 2021 else date.year)
    try:
        filename = get_filename(site, content)
        #filename = f'-filename:{get_filename(site, content)}'
        print(filename)
        if not args.debug:
            upload(site, content, filename, upload_content)
            '''result = file_page.upload(content.downloadUrl, text=upload_content, 
            comment="Uploading Generalitat de Catalunya Press Room image", 
            ignore_warnings=False, report_success=True) result = upload.main("-always", 
            filename, "-abortonwarn:", "-noverify", content.downloadUrl, upload_content)'''
    except AlreadyUploadedException as e:
        print(e)
    except pywikibot.exceptions.APIError as e:
        if "verification-error" in e.code:
            details = e.other['details']
            if details[0] == 'filetype-mime-mismatch':
                new_extension = details[2]
                match = re.match(r'image\/(.*?)$', new_extension)
                if match:
                    content.extension = "." + match.group(1)
                else:
                    content.extension = "." + details[2]
                print(f"Fixing verification-error: {filename}")
                upload_image(site, content)
        elif "duplicate" in e.code:
            if args.blacklist:
                idt = content.id
                file.write(f'{idt}\n')
            print(f"ContentId {idt} already uploaded with filename: {filename}")
        elif "exists-normalized" in e.code:
            content.title = f"GENCAT - {content.title} ({content.id})"
            print(f"Fixing exists-normalized: {filename}")
            upload_image(site, content)
        else:
            traceback.print_exc()
            print(e.args)
            print(e.info)
            print(e.other)
            print(e.code)
            print("S'ha produït un error inesperat.")
    except Exception as e:
        traceback.print_exc()
        print("Exception: S'ha produït un error inesperat.")
    '''(before api error) except pywikibot.exceptions.UploadError:
        traceback.print_exc()
        print("UploadError: S'ha produït un error inesperat.")'''

def query_page(last_element):
    time.sleep(randint(3, 10))
    query = GENCAT_API_QUERY.substitute(
        start=strdate_to_datetime_utc(args.start_date),
        end=strdate_to_datetime_utc(args.end_date),
        after='' if last_element is None else f',"search_after":[{last_element}]')
    print(GENCAT_API_URL)
    print(query)
    json_query = json.loads(query)
    #print(json_query)
    response = requests.post(GENCAT_API_URL, json=json_query, timeout=40)
    if response.status_code != 200:
        raise Exception(f"Status Code {response.status_code}")
    #print(response.json())
    return response.json()

def is_blacklisted_image(idt, file_ids):
    return args.blacklist and idt in file_ids

def is_copyrighted_image(idt, file_ids):
    return idt in file_ids

def get_penultimate_sort_element(image_data):
    last_sort = image_data[-1]['sort'][0]
    count = 1
    for element in reversed(image_data[:-1]):
        if element['sort'][0] != last_sort:
            return element['sort'][0], count #penultimate_sort
        count += 1
    #FIXME: En no poder mantenir sessió, podria passar que es perdéssin encara algunes imatges.
    return last_sort, count

def get_image_data(response_data):
    try:
        response_data['hits']['hits']
    except KeyError as e:
        return None
    return response_data['hits']['hits']

def process_batch(site):
    copyrighted_ids = get_ids_file(copyrighted_images)
    if args.blacklist:
        blacklisted_ids = get_ids_file(file)
    response_data = query_page(None)
    image_data = get_image_data(response_data)
    partial_length = len(response_data['hits']['hits'])
    total = response_data['hits']['total']['value']
    iterator = 0
    reprocess_images = 0
    print(f"Processing {total} of images ...")
    while image_data and len(image_data) > 0:
        for element in image_data:
            content = parse_content_information(element)
            print(content.id)
            if not is_blacklisted_image(content.id, blacklisted_ids) and not is_copyrighted_image(content.id, copyrighted_ids):
                upload_image(site, content)
            iterator = iterator + 1
            print(f"Processed images: {iterator} of {total}")
        sort_id, reprocess_images = get_penultimate_sort_element(image_data)
        iterator -= reprocess_images
        print(f"Next sort Idt: {sort_id}, {reprocess_images} items will be reprocessed.")
        response_data = query_page(sort_id)
        image_data = get_image_data(response_data)
        if image_data:
            partial_length = partial_length + len(image_data)

def get_ids_file(file):
    file.seek(0)
    file_ids = file.read().split('\n')
    file.seek(0, 2)
    return file_ids

def main():
    site = pywikibot.Site("commons", "commons")
    site.login()
    process_batch(site)

if __name__ == '__main__':
    main()
#!/usr/bin/python
# -*- coding: utf-8 -*-

from paprika import *
from string import Template
from datetime import datetime
from scripts import upload
from urllib.parse import urlparse
from random import randint
import argparse
import os
import requests
import pywikibot
import json
import re
import time
import traceback

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
        return "https://govern.cat/salapremsa/audiovisual/imatge/{0}/{1}".format(self.catImage, self.id)

GENCAT_API_URL = "https://cercadorgovern.extranet.gencat.cat/documents-ca//_search"
GENCAT_API_QUERY = Template('{"sort":{"dataPublicacioPortal":{"order":"desc"}},"query":{"bool":{"must":[{"range":{"dataPublicacioPortal":{"format":"date_optional_time","gte":"${start}","lt":"${end}"}}}],"filter":[{"match":{"type.main":"5"}}],"must_not":[]}}${after}}')
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
    parser.add_argument("--start", dest="start_date", action="store", help="Data des del qual vols importar. Per exemple, 2023-10-12", required=True)
    parser.add_argument("--end", dest="end_date", action="store", help="Data fins qual vols importar (dia no inclòs). Per exemple, 2023-10-13", required=True)
    parser.add_argument("--blacklist", action="store_true", help="Genera una blacklist local que exclou els identificadors d'imatges afegits. També afegeix a la blacklist aquelles imatges que ja han estat carregades a Commons prèviament.")
    args = parser.parse_args()
    parser.print_help()
    return args

args = help()

if args.blacklist:    
    try:
        file = open('premsaGencat_ids.txt', 'a+', encoding='utf8')
    except (OSError, IOError) as e:
        print(u'Problemes per obrir l\'arxiu')
        exit(0)

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
    pattern = r'[fF][oO][tT][oO].?\d{1,2}\s*|[fF][oO][tT][oO]$|\.$| $'
    return re.fullmatch(pattern, filename)

def trunc_filename(filename):
    return (filename.encode('utf-8')[:MAX_BYTES].decode('utf-8') + "...") if len(filename.encode('utf-8')) > MAX_BYTES else filename

def get_file_extension(url):
    return os.path.splitext(urlparse(url).path)[1]

def filename_already_exists(site, filename, idt):
    page = pywikibot.FilePage(site, u"File:{0}".format(filename))
    if page.exists() and idt in page.get():
        if args.blacklist:
            print(idt)
            file.write('{0}\n'.format(idt))
        raise AlreadyUploadedException("ContentId {0} already uploaded with filename: {1}".format(idt, filename))
    else:
        return True if page.exists() else False

def parse_filename(filename):
    file = remove_not_allowed_characters(filename)
    if is_blacklisted(file):
        file = "Generalitat de Catalunya Press Room - " + file
    return trunc_filename(file)

def get_filename(site, content):
    filename_title = parse_filename(content.title)
    print(filename_title)
    date = strdatetime_to_date(content.publicationDate).strftime("%d-%m-%Y")
    filename = '{name} ({date}){extension}'.format(name=filename_title, #
        extension=content.extension, #
        date=date)
    print(filename)
    if not filename_already_exists(site, filename, content.id):
        return filename

    for i in range(10):
        filename = '{name} ({date}) - {i}{extension}'.format(name=filename_title, #
        extension=content.extension, #
        date=date, #
        i=i)
        if not filename_already_exists(site, filename, content.id):
            return filename

    print("NO HAURÍEM D'ARRIBAR AQUÍ")
    exits(0)

def upload(site, content, filename, upload_content):
    print(upload_content)
    file_page = pywikibot.FilePage(site, u"File:{0}".format(filename))
    file_page.upload(content.downloadUrl, text=upload_content, comment="Uploading Generalitat de Catalunya Press Room image", ignore_warnings=False, report_success=True)  

def upload_image(site, content):
    date = strdatetime_to_date(content.publicationDate)
    upload_content = UPLOAD_PAGE.substitute(title = content.title, #
        date='{{{{Published on|{0}}}}}'.format(date.date()), #
        author='{{Institution:Govern de Catalunya}}', #
        permission='{{Attribution-govern}}', #
        subtitle = content.subtitle, #
        agency = "/".join(content.agency), #
        source=content.get_source(), #
        datecat='{0} {1}'.format(date.strftime("%B"), date.year) if date.year > 2021 else date.year)
    try:
        filename = get_filename(site, content)
        #filename = '-filename:{0}'.format(get_filename(site, content))
        print(filename)
        if not args.debug:
            upload(site, content, filename, upload_content)
            #result = file_page.upload(content.downloadUrl, text=upload_content, comment="Uploading Generalitat de Catalunya Press Room image", ignore_warnings=False, report_success=True)
            #result = upload.main(u"-always", filename, u"-abortonwarn:", u"-noverify", content.downloadUrl, upload_content)
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
                print("Fixing verification-error: {0}".format(filename))
                upload_image(site, content)
        elif "duplicate" in e.code:
            if args.blacklist:
                idt = content.id
                file.write('{0}\n'.format(idt))
            print("ContentId {0} already uploaded with filename: {1}".format(idt, filename))
        elif "exists-normalized" in e.code:
            content.title = "GENCAT - {0} ({1})".format(content.title, content.id)
            print("Fixing exists-normalized: {0}".format(filename))
            upload_image(site, content)
        else:
            traceback.print_exc()
            print(e.args)
            print(e.info)
            print(e.other)
            print(e.code)
            print("S'ha produït un error inesperat.")
    except pywikibot.exceptions.UploadError as e:
        traceback.print_exc()
        print("UploadError: S'ha produït un error inesperat.")
    except Exception as e:
        traceback.print_exc()
        print("Exception: S'ha produït un error inesperat.")

def query_page(last_element):
    time.sleep(randint(3, 10))
    query = GENCAT_API_QUERY.substitute(
        start=strdate_to_datetime_utc(args.start_date),
        end=strdate_to_datetime_utc(args.end_date),
        after='' if last_element is None else ',"search_after":[{0}]'.format(last_element))
    print(GENCAT_API_URL)
    json_query = json.loads(query)
    response = requests.post(GENCAT_API_URL, json=json_query)
    if response.status_code != 200:
        raise Exception("Status Code {0}".format(r.status_code))
    return response.json()

def is_blacklisted_image(idt, file_ids):
    return args.blacklist and idt in file_ids

def process_batch(site):
    if args.blacklist:
        file_ids = blacklist_images()
    response_data = query_page(None)
    image_data = response_data['hits']['hits']
    partial_length = len(response_data['hits']['hits'])
    total = response_data['hits']['total']['value']
    iterator = 0
    print("Processing {0} of images ...".format(total))
    while len(image_data) > 0:
        for element in image_data:
            content = parse_content_information(element)
            if not is_blacklisted_image(content.id, file_ids): #FILE IDS POT NO EXISTIR 
                upload_image(site, content)
            iterator = iterator + 1
            print("Processed images: {0} of {1}".format(iterator, total))
        last_element_id = image_data[-1]['sort'][0]
        response_data = query_page(last_element_id)
        image_data = response_data['hits']['hits']
        partial_length = partial_length + len(response_data['hits']['hits'])
        print(partial_length)
        print("Progress: {0} of {1} images".format(partial_length, total))

def blacklist_images():
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
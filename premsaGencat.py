#!/usr/bin/python
# -*- coding: utf-8 -*-

from paprika import *
from string import Template
from datetime import datetime
from scripts import upload
import argparse
import requests
import pywikibot
import json

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
    height: str

    def get_source(self):
        return "https://govern.cat/salapremsa/audiovisual/imatge/2/{0}".format(self.id)

GENCAT_API_URL = "https://cercadorgovern.extranet.gencat.cat/documents-ca//_search"
GENCAT_API_QUERY = Template('{"sort":{"dataPublicacioPortal":{"order":"desc"}},"query":{"bool":{"must":[{"range":{"dataPublicacioPortal":{"format":"date_optional_time","gte":"${start}","lt":"${end}"}}}],"filter":[{"match":{"type.main":"5"}}],"must_not":[]}}}')
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

[[Category:Images from Generalitat de Catalunya Press Room in ${month} ${year}]]
    ''')

def help():
    parser = argparse.ArgumentParser(description="Exemple d'ús PremsaGencat.")
    parser.add_argument("--debug", action="store_true", help="No es pengen les imatges a Commons.")
    parser.add_argument("--start", dest="start_date", action="store", help="Data des del qual vols importar. Per exemple, 2023-10-12", required=True)
    parser.add_argument("--end", dest="end_date", action="store", help="Data fins qual vols importar (dia no inclòs). Per exemple, 2023-10-13", required=True)
    args = parser.parse_args()
    parser.print_help()
    return args

args = help()

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
        extension=element['_source']['multimedia']['extensio'],
        publicationDate=element['_source']['dataPublicacioPortal'],
        agency=parse_agencies(element['_source']['departaments'])
        )

def filename_already_exists(site, filename, idt):
    page = pywikibot.Page(site, u"File:{0}".format(filename))
    if page.exists() and idt in page.get():
        raise AlreadyUploadedException("ContentId {0} already uploaded with filename: {1}".format(idt, filename))
    else:
        return True if page.exists() else False

def get_filename(site, content):
    date = strdatetime_to_date(content.publicationDate).strftime("%d-%m-%Y")
    filename = '{name} ({date}).{extension}'.format(name=content.title, #
        extension=content.extension, #
        date=date)
    print(filename)
    if not filename_already_exists(site, filename, content.id):
        return filename

    for i in range(10):
        print(i)
        filename = '{name} ({date}) - {i}.{extension}'.format(name=content.title, #
        extension=content.extension, #
        date=date, #
        i=i)
        print(filename)
        if not filename_already_exists(site, filename, content.id):
            return filename

    print("NO HAURÍEM D'ARRIBAR AQUÍ")
    exits(0)

def upload_image(site, content):
    date = strdatetime_to_date(content.publicationDate)
    upload_content = UPLOAD_PAGE.substitute(title = content.title, #
        date='{{{{Published on|{0}}}}}'.format(date.date()), #
        author='{{Institution:Govern de Catalunya}}', #
        permission='{{Attribution-govern}}', #
        subtitle = content.subtitle, #
        agency = "/".join(content.agency), #
        source=content.get_source(), #
        month=date.strftime("%B"), #
        year = date.year)
    print(upload_content)
    try:
        filename = '-filename:{0}'.format(get_filename(site, content))
        if not args.debug:
            upload.main(u"-always", filename, u"-abortonwarn:", u"-noverify", content.downloadUrl, upload_content)
    except AlreadyUploadedException as e:
        print(e)

def process(site):
    query = GENCAT_API_QUERY.substitute(
        start=strdate_to_datetime_utc(args.start_date),
        end=strdate_to_datetime_utc(args.end_date))
    json_query = json.loads(query)
    print(GENCAT_API_URL)
    print(json_query)
    r = requests.post(GENCAT_API_URL, json=json_query)

    if r.status_code == 200:
        response_data = r.json()
        total = len(response_data['hits']['hits'])
        print("Processed images: 0 de {0}".format(total))
        processed = 0
        for element in response_data['hits']['hits']:
            content = parse_content_information(element)
            upload_image(site, content)
            processed = processed + 1
            print("Processed images: {0} de {1}".format(processed, total))

def main():
    site = pywikibot.Site("commons", "commons")
    site.login()

    process(site)

if __name__ == '__main__':
	main()
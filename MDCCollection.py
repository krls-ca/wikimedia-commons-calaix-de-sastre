#!/usr/bin/python
# -*- coding: utf-8 -*-
import argparse
import urllib.request
import re
import requests
import os
import io
from html.parser import HTMLParser
from scripts import upload
import pywikibot
import json

def help():
	parser = argparse.ArgumentParser(description="Exemple d'ús MDCCollection.")
	parser.add_argument("--force", action="store_true", help="Força tornar a executar l'execució get_all_collection_links.")
	parser.add_argument("--debug", action="store_true", help="No es pengen les imatges a Commons.")
	parser.add_argument("--author", action="store", help="Author name in Wikimedia Commons. Ex: 'Antoni Bartumeus i Casanovas'." , required=True)
	parser.add_argument("--authormdc", action="store", help="Author name in MDC Collection. Ex: 'Bartomeus i Casanovas, Antoni, 1856-1935'." , required=True)
	parser.add_argument("--dir", action="store", help="Local name folder. Ex 'BartumeusCasanovas'.", required=True)
	parser.add_argument("--license", action="store", help="License Ex: 'PD-old-80'.", required=False, default='PD-old-80')
	parser.add_argument("--authorcat", action="store", help="Custom naming in Category:Photographs by ...", required=False)
	args = parser.parse_args()
	parser.print_help()
	return args

args = help()
AUTHOR_DIR = args.dir
FULL_NAME_AUTHOR = args.author
DOMAIN = u"https://mdc.csuc.cat/digital"
JSON_URL = 'https://mdc.csuc.cat/digital/api/search/collection/afceccf!afcecemc!afcecag!afcecin!afceco!afcecpz/searchterm/{mdc}/field/creato/mode/all/conn/and/order/title/ad/asc/maxRecords/8000'.format(mdc=urllib.parse.quote(args.authormdc))
JSON_METADATA_URL = 'https://mdc.csuc.cat/digital/api/collections/{collection}/items/{id}/true'
IMG_FOLDER = u"MDC/{author}/images/".format(author=AUTHOR_DIR)
LICENSE = u"{{{{PD-Art|{license}}}}}".format(license=args.license)
INSTITUTION = u"{{Institution:Memòria Digital de Catalunya}}"
FONDS = u'Fons'
COMMONS_CAT = u"[[Category:Photographs by {author}]]\n[[Category:Images from Memòria Digital de Catalunya]]".format(author=args.authorcat if args.authorcat else args.author)

class CompoundObjectException(Exception):
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super(CompoundObjectException, self).__init__(message)

try:
	collection_url_file = open(u'MDC/{0}/{0}-urls.txt'.format(AUTHOR_DIR), 'a+', encoding='utf8')
	done_file = open(u'MDC/{0}/done.txt'.format(AUTHOR_DIR), 'a+', encoding='utf8')
	fail_file = open(u'MDC/{0}/fail.txt'.format(AUTHOR_DIR), 'a+', encoding='utf8')
except (OSError, IOError) as e:
	print(u'Problemes per obrir l\'arxiu')
	exit(0)

def download_image_to_file(image_url, output_file):
    """Download image from url"""
    if not (os.path.isfile(u'{0}jpeg'.format(output_file)) or os.path.isfile(u'{0}png'.format(output_file))):
	    r = requests.get(image_url, stream=True)
	    if r.status_code == 200:
	        image_type = r.headers['content-type']
	        if image_type == 'image/jpeg':
	            image_ext = 'jpeg'
	        else:
	          if image_type == 'image/png':
	              image_ext = 'png'
	        output_file_ext = output_file + image_ext

	        with open(output_file_ext, 'wb') as f:
	          for chunk in r.iter_content(chunk_size=8192):
	              f.write(chunk) #verify_image
	        if os.path.getsize(u'{0}'.format(output_file_ext)) == 0:
	        	os.remove(output_file_ext)
	        	raise CompoundObjectException("Objecte CompoundObject")
	    else:
	        exit(0)

def scrap_results_page(content):
	link_pages = set()
	jsonObjectItems = json.loads(content)
	for elem in jsonObjectItems['items']:
		link = elem[u'itemLink']
		link_pages.add(DOMAIN + link.replace("/singleitem", "").replace("/compoundobject", ""))
	return link_pages

def write_image_urls(img_urls):
	for url in img_urls:
		collection_url_file.write('{0}\n'.format(url))

def get_unique_identifiers(img_url):
	unique_id = re.search('collection\/(.*?)\/id\/(.*?)$', img_url)
	collection, identifier = unique_id.group(1), unique_id.group(2)
	return (collection, identifier)

def description_text(meta):
	header = u"== {{int:filedesc}} ==\n\n"
	description = u"{{{{Photograph \n |photographer       = {0} \n |title              = {{{{ca|{1}}}}} \n |description        = {{{{ca|{2}}}}} \n |depicted people    = \n |depicted place     = {3}"\
	"\n |date               = {4} \n |medium             = {12} \n |dimensions         = {13}\n |institution        = {5} \n |department         = {6}"\
	"\n |credit line        = {7} (depositor) \n |inscriptions       = \n |accession number   = {8} \n |source             = {9} \n |permission         = {10} "\
	"\n |other_versions     = \n |original description = {11}\n |wikidata           = \n}}}}\n\n"\
	"".format(u"{{{{Creator:{0}}}}}".format(FULL_NAME_AUTHOR), meta.get("title"), meta.get("description"), \
		meta.get("geo"), meta.get("publishedDate"), INSTITUTION, meta.get("fonds"), \
		meta.get("depositor"), meta.get("inventaryNumber"), meta.get("source"), LICENSE, meta.get("originalDescription"), meta.get("medium"), meta.get("dimensions"))
	#license = u"== {{{{int:license-header}}}} ==\n{0}\n\n".format(LICENSE)
	license = u""
	return header + description + license + meta.get("commonCat")

def file_exists(site, filename):
	page = pywikibot.Page(site, u"File:{0}".format(filename))
	return page.exists()

def remove_not_allowed_characters(title):
	characters_to_remove = "#<>[]|:{}"
	return title.translate(str.maketrans('', '', characters_to_remove))

def upload_image(site, meta, img_path):
	description = description_text(meta)
	if os.path.isfile(u'{0}jpeg'.format(img_path)):
		img_path = u'{0}jpeg'.format(img_path)
		name_file = u'-filename:{0}.jpeg'.format(meta.get("title"))
		file_name = u'{0}.jpeg'.format(meta.get("title"))
		alternative_file_name = u'{0} ({1}).jpeg'.format(meta.get("title"), meta.get("inventaryNumber"))
		alternative_name_file = u'-filename:{0} ({1}).jpeg'.format(meta.get("title"), meta.get("inventaryNumber"))
	elif os.path.isfile(u'{0}png'.format(img_path)):
		img_path = u'{0}png'.format(img_path)
		name_file = u'-filename:{0}.png'.format(meta.get("title"))
		file_name = u'{0}.png'.format(meta.get("title"))
		alternative_file_name = u'{0} ({1}).png'.format(meta.get("title"), meta.get("inventaryNumber"))
		alternative_name_file = u'-filename:{0} ({1}).png'.format(meta.get("title"), meta.get("inventaryNumber"))
	else:
		exit(0)
	page = pywikibot.Page(site, u"File:{0}".format(file_name))

	if(not args.debug):
		if page.exists():
			if page.isRedirectPage() or meta.get("inventaryNumber") not in page.get():
				page = pywikibot.Page(site, u"File:{0}".format(alternative_file_name))
				if not page.exists():
					print(alternative_name_file)
					upload.main(u"-always", alternative_name_file, u"-abortonwarn:", u"-noverify", img_path, description)
					if file_exists(site, alternative_file_name):
						done_file.write('{0}\n'.format(meta.get('source')))
					else:
						print("HA FALLAT {0}".format(alternative_file_name))
						fail_file.write('{0}\n'.format(meta.get('source')))
				else:
					done_file.write('{0}\n'.format(meta.get('source')))
			else:
				done_file.write('{0}\n'.format(meta.get('source')))
		else:
			print(page.exists())
			upload.main(u"-always", name_file, u"-abortonwarn:", u"-noverify", img_path, description)
			#We got the following warning(s): exists-normalized: File exists with different extension as "Platja_de_Badalona.JPG".
			if file_exists(site, file_name):
				done_file.write('{0}\n'.format(meta.get('source')))
			else:
				print("HA FALLAT {0}".format(file_name))
				fail_file.write('{0}\n'.format(meta.get('source')))

def parse_description(data):
	date = u"''{0}''. {1}".format(get_meta_field(data, "title"), 
		FULL_NAME_AUTHOR)
	return date + ' ({0})'.format(parse_date(get_meta_field(data, "date"))) if parse_date(get_meta_field(data, "date")) else date

def parse_dimensions(mats):
	materials = mats.split(";")
	return next(
		(mat.strip() for mat in materials 
			if " x " in mat), None)

def parse_date(date):
	if date is not None:
		found = re.search('\[(.*?)\]', date)
		if found:
			return found.group(1)
		else:
			return date
	return date

def get_meta_field(data, key):
	return next(
		(field["value"].strip() for field in data["fields"] 
			if field["key"] == key), None)

def get_compound_id(collection, identifier):
	metadata_url = JSON_METADATA_URL.format(collection=collection, id=identifier)
	html_content = urllib.request.urlopen(metadata_url)
	content = html_content.read()
	data = json.loads(content)
	return data["id"]

def get_metadata(collection, identifier, img_url):
	metadata_url = JSON_METADATA_URL.format(collection=collection, id=identifier)
	html_content = urllib.request.urlopen(metadata_url)
	content = html_content.read()
	data = json.loads(content)
	#FIXME: Números d'inventari de afcecag
	#Default is afceccf
	meta = dict(
		inventaryNumber = get_meta_field(data, "subjec"),
		description = parse_description(data),
		originalDescription = get_meta_field(data, "descri"),
        title = remove_not_allowed_characters(get_meta_field(data, "title")),
        photographer = FULL_NAME_AUTHOR,
        fonds = u'{0} {1}'.format(FONDS, get_meta_field(data, "identi")),
        medium = get_meta_field(data, "format"), 
        dimensions = parse_dimensions(get_meta_field(data, "format")),
        publisher = get_meta_field(data, "reposi"),
        geo = get_meta_field(data, "ageo"),
        publishedDate = parse_date(get_meta_field(data, "date")),
        depositor = get_meta_field(data, "instit"),
        source = img_url,
        repository = u"Memòria Digital de Catalunya",
        subjec = get_meta_field(data, "subjec"),
        commonCat = COMMONS_CAT
        )
	if u"/afcecag/" in img_url:
		meta['inventaryNumber'] = get_meta_field(data, "creato")
	if u"/afcecemc/" in img_url:
		meta['inventaryNumber'] = get_meta_field(data, "identi")
		meta['originalDescription'] = get_meta_field(data, "ttol")
		meta['fonds'] = u'{0} {1}'.format(FONDS, get_meta_field(data, "fons"))
		meta['medium'] = get_meta_field(data, "descrb")
		meta['dimensions'] = parse_dimensions(get_meta_field(data, "descrb"))
		meta['depositor'] = get_meta_field(data, "publis")
	return meta

def process_image(site, img_url):
	print("Processing {0}".format(img_url))
	collection, identifier = get_unique_identifiers(img_url)
	output_path = u'{0}{1}-{2}-{3}.'.format(IMG_FOLDER, AUTHOR_DIR, collection, identifier)
	#image_url = "http://mdc.csuc.cat/utils/ajaxhelper/?CISOROOT={0}&CISOPTR={1}"\
		#"&action=2&DMWIDTH=5000&DMHEIGHT=5000&DMX=0&DMY=0&DMTEXT=&DMROTATE=0".format(collection, identifier)
	image_url = "https://mdc.csuc.cat/digital/download/collection/{collection}/id/{id}/size/full".format(collection=collection, id=identifier)

	try:
		download_image_to_file(image_url, output_path)
	except CompoundObjectException as e:
		first_id = get_compound_id(collection, identifier)
		compound_url = image_url.replace(identifier, str(first_id))
		print("CompoundObject {0}".format(compound_url))
		download_image_to_file(compound_url, output_path)

	if(u"/afceccf/" in img_url or u"/afcecag/" in img_url or u"/afcecemc/" in img_url):
		meta = get_metadata(collection, identifier, img_url)
		print(meta)
		if not args.debug:
			upload_image(site, meta, output_path)
	else:
		fail_file.write('{0}\n'.format(img_url))

def get_all_collection_links():
	html_content = urllib.request.urlopen(JSON_URL)
	content = html_content.read()
	image_urls = scrap_results_page(content)
	write_image_urls(image_urls)

def get_progress():
	collection_url_file.seek(0)
	collection_urls = collection_url_file.read().split('\n')
	collection_url_file.seek(0, 2)
	done_file.seek(0)
	done_urls = done_file.read().split('\n')
	done_file.seek(0, 2)
	fail_file.seek(0)
	fail_urls = fail_file.read().split('\n')
	fail_file.seek(0, 2)
	return collection_urls, done_urls, fail_urls

def is_empty_file(file):
	point = file.tell()
	file.seek(0)
	length = len(file.read())
	file.seek(point)
	return length == 0

def main():
	site = pywikibot.Site("commons", "commons")
	site.login()

	if is_empty_file(collection_url_file) or args.force:
		get_all_collection_links()

	collection_urls, done_urls, fail_urls = get_progress()
	processed = len(done_urls)-1
	for img_url in collection_urls:
		if img_url not in done_urls and img_url not in fail_urls:
			print(processed)
			process_image(site, img_url)
			processed = processed + 1
			print("PROCESSADES: {0}".format(processed))
	print("TOTAL: {0}".format(len(done_urls)))

if __name__ == '__main__':
	main()
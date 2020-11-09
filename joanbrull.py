#!/usr/bin/python
# -*- coding: utf-8 -*-
import pwb
import pywikibot
import sys
import os
import codecs
import json
import re
import urllib2
import upload

try:
	f1 = codecs.open('fotos2joanbrull', 'r', 'utf8')
except (OSError, IOError) as e:
	print u'No trobo el fitxer o no el sé obrir.'
	exit(0) 

txt = f1.read()
f1.close()
titol = re.findall(u'\?obra=(.*?)&amp;id_obra=', txt)
print len(titol)
ids = re.findall(u'\/medium\/(.*?)\.jpg', txt)
print len(ids)
anys = re.findall(u'<\/cite><\/a>(.*?)<br>', txt)
print len(anys)
dimensions = re.findall(u'<br>\n(.*?)</figcaption>', txt)
print len(dimensions)
contador = 0
for foto in ids:
	print contador
	#if contador > -1 and contador != 76:
	if contador == 76:
		file_name = titol[contador].replace(u'&quot;', '')
		print file_name
		'''try:
			url = ("http://joanbrull.com/images/joan_brull_obra/high/%s.jpg" % foto)
			file_name = titol[contador].replace(u'&quot;', '')
			u = urllib2.urlopen(url)
		except:
			try:
				url = ("http://joanbrull.com/images/joan_brull_obra/med-high/%s.jpg" % foto)
				file_name = titol[contador].replace(u'&quot;', '')
				u = urllib2.urlopen(url)
			except:
				print "PRINGADAAAAA %s" (foto)
		try:
			intermitja = u'joan/%s - Joan Brull i Vinyoles (1863-1912).jpg' % (file_name)
			if os.path.isfile(intermitja):
				numero = 0
				while os.path.isfile(intermitja):
					intermitja = u'joan/%s - Joan Brull i Vinyoles (1863-1912) - %d.jpg' % (file_name, numero)
					numero = numero + 1
			f = open(intermitja, 'wb')
		except:
			try:
				intermitja = u'joan/%s - Joan Brull i Vinyoles (1863-1912).jpg' % (file_name.encode('utf-8'))
				if os.path.isfile(intermitja):
					numero = 0
					while os.path.isfile(intermitja):
						intermitja = u'joan/%s - Joan Brull i Vinyoles (1863-1912) - %d.jpg' % (file_name, numero)
						numero = numero + 1
				f = open(intermitja, 'wb')
			except:
				print "SENSE FER RES "
		meta = u.info()
		file_size = int(meta.getheaders("Content-Length")[0])
		print "Downloading: %s Bytes: %s" % (file_name, file_size)
		file_size_dl = 0
		block_sz = 8192
		while True:
			buffer = u.read(block_sz)
			if not buffer:
				break
			file_size_dl += len(buffer)
			f.write(buffer)
			status = r"%10d  [%3.2f%%]" % (file_size_dl, file_size_dl * 100. / file_size)
			status = status + chr(8)*(len(status)+1)
			print status,
		f.close()'''
	
		keep = u'-keep'
		target = u"-noverify"
		ignorewarn1 = u'-abortonwarn:duplicate'
		ignorewarn2 = u'-abortonwarn:exists'
		nomFitxerDirectori = u'joan/%s - Joan Brull i Vinyoles (1863-1912).jpg' % (file_name)
		nomFitxer = u'-filename:%s - Joan Brull i Vinyoles (1863-1912).jpg' % (file_name)
		if not os.path.isfile(nomFitxerDirectori):
			numero = 0
			while not os.path.isfile(nomFitxerDirectori) and numero < 8:
				nomFitxerDirectori = u'joan/%s - Joan Brull i Vinyoles (1863-1912) - %s.jpg' % (file_name, numero)
				nomFitxer = u'-filename:%s - Joan Brull i Vinyoles (1863-1912) - %s.jpg' % (file_name, numero)
				numero = numero + 1
		if os.path.isfile(nomFitxerDirectori):
			descripcio = u'{{Artwork\n |artist\t= {{Creator:%s}}\n |title\t= {{ca|%s}}\n |description\t= {{ca|1=\'\'%s\'\'}}\n |date\t= %s\n |medium\t= \n |dimensions\t= %s \n |institution\t= \n |department\t=\n |references\t=\n |object history\t=\n |exhibition history = \n |credit line\t=\n |inscriptions\t=\n |notes\t=\n |accession number\t= \n |place of creation\t= \n |source\t=[http://joanbrull.com/ca/cataleg-de-obres-de-joan-brull-i-vinyoles.php Catàleg d\'obres de joan brull i vinyoles] \n |permission\t={{PD-Art|1=PD-old-auto-1996|deathyear=1912}} \n |other_versions\t= }}\n[[Category:Joan Brull i Vinyoles]]' % (u'Joan Brull i Vinyoles', file_name, file_name, anys[contador].strip(), dimensions[contador].strip())
			print descripcio
			try:
				upload.main(keep, nomFitxer, target, ignorewarn1, ignorewarn2, nomFitxerDirectori, descripcio)
				os.remove(nomFitxerDirectori)
			except (verification-error):
				linia = "Fitxer ja penjat anteriorment: %s" % linia
		else:
			print "NO TROBAT"
	contador = contador + 1
	

# Calaix de Sastre - Viquitexts

> :warning: **AVERTÈNCIA:** Aquests són alguns dels codis no formals que he anat creant des que vaig començar a fer petits codis de manteniment per al Viquitexts el 2006. Una part d'ells no s'han mantingut des de la seva creació i poden no ser ja compatibles amb la versió actual del pywikibot. S'adjunten en aquest repositori per raons històriques i per si poden servir d'inspiració a d'altres en un futur.

Els codis tenen com a dependencia la llibreria pywikibot: https://www.mediawiki.org/wiki/Manual:Pywikibot/ca.

Calaix de sastre dels diferents projectes Wikimedia:
1. [Calaix de Sastre Viquipèdia](https://github.com/krls-ca/viquipedia-calaix-de-sastre)
2. [Calaix de Sastre Wikimedia Commons](https://github.com/krls-ca/viquipedia-calaix-de-sastre)
3. [Calaix de Sastre Wikidata](https://github.com/krls-ca/viquipedia-calaix-de-sastre)
4. [Calaix de Sastre Viquitexts](https://github.com/krls-ca/viquipedia-calaix-de-sastre)
5. [Calaix de Sastre Viquidites](https://github.com/krls-ca/viquipedia-calaix-de-sastre)

## Scrapping JoanBrull (2015)

Codi redumentari que es descarregava les fotogràfies en domini públic de Joan Brull (https://joanbrull.com/ca/) a partir del codi HTML de la pàgina d'aquell moment. Posteriorment, aquestes eren pujades a Wikimedia Commons amb les metadades bàsiques. https://commons.wikimedia.org/wiki/Category:Joan_Brull_i_Vinyoles

```sh
$ python joanBrull.py
```
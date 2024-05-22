# Calaix de Sastre - Wikimedia Commons

> :warning: **AVERTÈNCIA:** Aquests són alguns dels codis no formals que he anat creant des que vaig començar a fer petits codis de manteniment per a Wikimedia Commons el 2006. Una part d'ells no s'han mantingut des de la seva creació i poden no ser ja compatibles amb la versió actual del pywikibot. S'adjunten en aquest repositori per raons històriques i per si poden servir d'inspiració a d'altres en un futur.

Els codis tenen com a dependencia la llibreria pywikibot: https://www.mediawiki.org/wiki/Manual:Pywikibot/ca.

Calaix de sastre dels diferents projectes Wikimedia:
1. [Calaix de Sastre Viquipèdia](https://github.com/krls-ca/viquipedia-calaix-de-sastre)
2. [Calaix de Sastre Wikimedia Commons](https://github.com/krls-ca/viquipedia-calaix-de-sastre)
3. [Calaix de Sastre Wikidata](https://github.com/krls-ca/viquipedia-calaix-de-sastre)
4. [Calaix de Sastre Viquitexts](https://github.com/krls-ca/viquipedia-calaix-de-sastre)
5. [Calaix de Sastre Viquidites](https://github.com/krls-ca/viquipedia-calaix-de-sastre)


## arxivador-cawiki.py (històric; Coet)

Codi que arxiva les pàgines de discussió de la Viquipèdia en català.

## Semibot - Treure enllaços interwikis (2018)
Va ser un semibot per automatitzar el procés de manteniment d'eliminar enllaços interwiki dins el codi de l'article: ja fos eliminant l'enllaç directament, enllaçant amb l'article correcte en català o deixant-lo com un enllaç en blanc. Va ser un codi vinculat a la Gran Quinzena Anual de la Qualitat 2018.

## Scrapping JoanBrull (2015)

Codi redumentari que es descarregava les fotogràfies en domini públic de Joan Brull (https://joanbrull.com/ca/) a partir del codi HTML de la pàgina d'aquell moment. Posteriorment, aquestes eren pujades a Wikimedia Commons amb les metadades bàsiques. https://commons.wikimedia.org/wiki/Category:Joan_Brull_i_Vinyoles

```sh
$ python joanBrull.py
```

## Scrapping Memòria Digital Catalunya - Arxiu Fotogràfic de Catalunya (2019-2023)

És un codi rudimentari que s'encarrega de descarregar totes les imatges donada una cerca del Memòria Digital Catalunya (MDC), recupera les seves metadades de l'API de la MDC i finalment les penja a Commons. Aquest codi, requereix modificar les variables globals (en un futur es podria parametritzar) cas a cas. Aquest és específic per l'arxiu Arxiu Fotogràfic de Catalunya, perquè cada documentalista ha usat claus diferents per un mateix concepte a l'hora d'elaborar cada catàleg.

Forma part del projecte: https://commons.wikimedia.org/wiki/Commons:Wikiproject_Mem%C3%B2ria_Digital_de_Catalunya

- 1a versió (2019)
- 2a versió (2023)

Exemple d'ús MDCCollection:

```sh
$ python3 MDCCollection.py --author "Antoni Bartumeus i Casanovas" --authormdc "Bartomeus i Casanovas, Antoni, 1856-1935" --dir BartumeusCasanovas
```

Usage: MDCCollection.py [-h] [--force] [--debug] --author AUTHOR --authormdc AUTHORMDC --dir DIR

Arguments:
  -h, --help            show this help message and exit
  --force               Força tornar a executar l'execució get_all_collection_links
  --debug               No es pengen les imatges a Commons
  --author AUTHOR       Author name in Wikimedia Commons
  --authormdc AUTHORMDC
                        Author name in MDC Collection
  --dir DIR             Local name folder


## Sala de Premsa del Govern de Catalunya (2023)

És un codi que donat una rang de dates recupera les fotografies publicades en aquell període per la Sala de Premsa del Govern de Catalunya i les penja a Wikimedia Commons. S'eviten les imatges duplicades a partir de l'identificador de la fotografia al sistema.

```sh
$ python3 premsaGencat.py --start 1-10-2023 --end 1-11-2023
```

Usage: premsaGencat.py [-h] [--debug] --start START_DATE --end END_DATE

Exemple d'ús Premsa Gencat.

options:
  -h, --help          show this help message and exit
  --debug             No es pengen les imatges a Commons.
  --start START_DATE  Data des del qual vols importar. Per exemple, 2023-10-12
  --end END_DATE      Data fins qual vols importar (dia no inclòs). Per exemple, 2023-10-13
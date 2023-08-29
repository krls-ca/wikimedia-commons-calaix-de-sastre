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

## Scrapping Memòria Digital Catalunya - Arxiu Fotogràfic de Catalunya (2019-2023)

És un codi rudimentari que s'encarrega de descarregar totes les imatges donada una cerca del Memòria Digital Catalunya (MDC), recupera les seves metadades de l'API de la MDC i finalment les penja a Commons. Aquest codi, requereix modificar les variables globals (en un futur es podria parametritzar) cas a cas. Aquest és específic per l'arxiu Arxiu Fotogràfic de Catalunya, perquè cada documentalista ha usat claus diferents per un mateix concepte a l'hora d'elaborar cada catàleg.

Forma part del projecte: https://commons.wikimedia.org/wiki/Commons:Wikiproject_Mem%C3%B2ria_Digital_de_Catalunya

- 1a versió (2019)
- 2a versió (2023)

```sh
$ python3 MDCCollection.py
```
--debug: no penja les fotografies a Commons
--force: encara que ja s'hagi descarregat l'imatge es torna a descarregar

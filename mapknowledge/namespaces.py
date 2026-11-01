#===============================================================================
#
#  Flatmap viewer and annotation tools
#
#  Copyright (c) 2019-21  David Brooks
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
#===============================================================================

import rdflib

#===============================================================================

class NAMESPACES:
    namespaces = {
        'apinatomy' : 'https://apinatomy.org/uris/readable/',
        'JAX'       : 'http://jaxmice.jax.org/strain/',
        'NCBITaxon' : 'http://purl.obolibrary.org/obo/NCBITaxon_',
        'PATO'      : 'http://purl.obolibrary.org/obo/PATO_',
        'UBERON'    : 'http://purl.obolibrary.org/obo/UBERON_',
        'CL'        : 'http://purl.obolibrary.org/obo/CL_',
        'PR'        : 'http://purl.obolibrary.org/obo/PR_',
        'FMA'       : 'http://purl.org/sig/ont/fma/fma',
        'CHEBI'     : 'http://purl.obolibrary.org/obo/CHEBI_',
        'NCBIGene'  : 'http://www.ncbi.nlm.nih.gov/gene/',
        'PMID'      : 'http://www.ncbi.nlm.nih.gov/pubmed/',
        'TEMPIND'   : 'http://uri.interlex.org/temp/uris/phenotype-indicators/',
        'TEMP'      : 'http://uri.interlex.org/temp/uris/',
        'RRID'      : 'https://scicrunch.org/resolver/RRID:',
        'femrep'    : 'http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/femrep/',
        'kidney'    : 'http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/kidney/',
        'liver'     : 'http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/liver/',
        'mmset1'    : 'http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/mmset1/',
        'mmset2cn'  : 'http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/mmset2cn/',
        'mmset4'    : 'http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/mmset4/',
        'prostate'  : 'http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/prostate/',
        'semves'    : 'http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/semves/',
        'senmot'    : 'http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/senmot/',
        'swglnd'    : 'http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/swglnd/',
        'ilxtr'     : 'http://uri.interlex.org/tgbugs/uris/readable/',
        'gastint'   : 'http://uri.interlex.org/composer/uris/set/gastint/',
        'pain1'     : 'http://uri.interlex.org/composer/uris/set/pain1/',
        'pain2'     : 'http://uri.interlex.org/composer/uris/set/pain2/',
        'portal'    : 'http://uri.interlex.org/composer/uris/set/portal/',
        'npokb'     : 'http://uri.interlex.org/npo/uris/neurons/',
        'ILX'       : 'http://uri.interlex.org/base/ilx_',
        'ilx'       : 'http://uri.interlex.org/',   # More general need to be ordered later
        'rdfs'      : str(rdflib.RDFS),
        'rdf'       : str(rdflib.RDF),
    }

    @staticmethod
    def uri(curie: str) -> str:
        parts = curie.split(':', 1)
        if len(parts) == 2 and parts[0] in NAMESPACES.namespaces:
            return NAMESPACES.namespaces[parts[0]] + parts[1]
        return curie

    @staticmethod
    def curie(uri: str) -> str:
        for prefix, ns_uri in NAMESPACES.namespaces.items():
            if uri.startswith(ns_uri):
                return f'{prefix}:{uri[len(ns_uri):]}'
        return uri

#===============================================================================

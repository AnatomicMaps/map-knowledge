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

class NAMESPACES:
    namespaces = {
        'ILX': 'http://uri.interlex.org/base/ilx_',
        'NCBITaxon': 'http://purl.obolibrary.org/obo/NCBITaxon_',
        'PATO': 'http://purl.obolibrary.org/obo/PATO_',
        'UBERON': 'http://purl.obolibrary.org/obo/UBERON_',
        'apinatomy': 'https://apinatomy.org/uris/readable/',
        'ilxtr': 'http://uri.interlex.org/tgbugs/uris/readable/',
        'ilx': 'http://uri.interlex.org/',   # More general need to be ordered later
        'CL': 'http://purl.obolibrary.org/obo/CL_',
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

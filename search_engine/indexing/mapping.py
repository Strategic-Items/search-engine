"""Index definitions. Synonyms expand at search time, so the dictionary can
change without reindexing the documents themselves."""

# Lucene's defaults keep VX, VCP and VCN, so a conversational ending survives
# as a search term: "알려줘" tokenizes to 알리(VV) + 어(EC) + 주(VX) + 어(EC),
# and the 주 it leaves behind matches the "주 :" that heads a table note.
# Because 주 is rare in titles its IDF is high, so that one token can outscore
# a real match on every content word and then push the ratio cutoff above the
# documents that did match. Auxiliary verbs and copulas carry no topic.
KOREAN_POS_FILTER = {
    "type": "nori_part_of_speech",
    # Lucene's default list, spelled out -- "E" and "J" are abstract categories
    # this version rejects, so the concrete endings and particles are named --
    # plus VX, VCP and VCN.
    "stoptags": [
        # verbal endings and particles: Lucene's defaults
        "EC", "EF", "EP", "ETM", "ETN",
        "JC", "JKB", "JKC", "JKG", "JKO", "JKQ", "JKS", "JKV", "JX",
        "IC", "MAG", "MAJ", "MM", "SP", "SSC", "SSO", "SC", "SE",
        "XPN", "XSA", "XSN", "XSV", "UNA", "NA", "VSV",
        # added here: auxiliary verbs and copulas carry no topic
        "VX", "VCP", "VCN",
    ],
}


def index_body(embedding_dimensions: int) -> dict:
    """Core mapping, including an HNSW cosine vector index."""
    return {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "index": {"knn": True},
        "analysis": {
            "filter": {
                "domain_synonyms": {"type": "synonym_graph", "synonyms": []},
                "korean_pos": KOREAN_POS_FILTER,
            },
            "analyzer": {
                "korean_nori": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["korean_pos", "lowercase"],
                },
                # Synonyms expand before the part-of-speech filter: that filter
                # drops tokens, leaving position gaps a synonym graph cannot be
                # built from (자가판정 -> 자_0, 판정_2).
                "korean_nori_search": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["lowercase", "domain_synonyms", "korean_pos"],
                },
            }
        }
    },
    "mappings": {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "parent_id": {"type": "keyword"},
            # Titles stay literal: form queries name a document's title almost
            # word for word, and expanding those turns a precise match into a
            # fuzzy one. Bodies carry the vocabulary gap, so they expand.
            "title": {
                "type": "text", "analyzer": "korean_nori",
                "fields": {"standard": {"type": "text", "analyzer": "standard"}},
            },
            "body": {
                "type": "text", "analyzer": "korean_nori",
                "search_analyzer": "korean_nori_search",
                "fields": {"standard": {"type": "text", "analyzer": "standard"}},
            },
            "code_norm": {"type": "keyword"},
            "codes_exact": {"type": "keyword"},
            "source_type": {"type": "keyword"},
            "date_basis": {"type": "keyword"},
            "superseded_by": {"type": "keyword"},
            "source_url": {"type": "keyword", "index": False},
            "published_at": {"type": "date"},
            "effective_from": {"type": "date"},
            "effective_to": {"type": "date"},
            "content_hash": {"type": "keyword", "index": False},
            "embedding": {
                "type": "knn_vector",
                "dimension": embedding_dimensions,
                "method": {
                    "name": "hnsw", "engine": "faiss", "space_type": "cosinesimil",
                },
            },
        },
    },
    }


def callcenter_index_body(embedding_dimensions: int) -> dict:
    """Search mapping for past consultations, isolated from official sources."""
    body = index_body(embedding_dimensions)
    body["mappings"]["properties"].update({
        "call_id": {"type": "keyword"},
        "seq": {"type": "integer"},
        "call_inquiry": {"type": "text", "analyzer": "korean_nori"},
        "categories": {"type": "keyword"},
        "keywords": {"type": "keyword"},
        "start_sec": {"type": "float"},
        "end_sec": {"type": "float"},
        "seg_ids": {"type": "keyword", "index": False},
        # A nested mapping preserves type/value pairs for a future faceted UI.
        "entities": {"type": "nested", "properties": {
            "type": {"type": "keyword"},
            "mention": {"type": "text", "analyzer": "korean_nori"},
            "normalized": {"type": "keyword"},
            "seg_ids": {"type": "keyword", "index": False},
        }},
    })
    return body


# Preserve a directly inspectable default mapping for callers and tests.
HSK_INDEX_BODY = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "filter": {"korean_pos": KOREAN_POS_FILTER},
            "analyzer": {
                "korean_nori": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["korean_pos", "lowercase"],
                }
            }
        }
    },
    "mappings": {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "hsk_code": {"type": "keyword"},
            "control_no_norm": {"type": "keyword"},
            "control_number": {"type": "keyword"},
            "name_ko": {"type": "text", "analyzer": "korean_nori"},
            "name_en": {"type": "text", "analyzer": "standard"},
            "source_url": {"type": "keyword", "index": False},
            "retrieved_at": {"type": "date"},
            "linkage_notice": {"type": "text", "index": False},
        },
    },
}

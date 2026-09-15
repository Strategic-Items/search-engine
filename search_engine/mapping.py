"""Index definitions. Synonyms expand at search time, so the dictionary can
change without reindexing the documents themselves."""

INDEX_BODY = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "filter": {
                "domain_synonyms": {"type": "synonym_graph", "synonyms": []},
            },
            "analyzer": {
                "korean_nori": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["nori_part_of_speech", "lowercase"],
                },
                # Synonyms expand before the part-of-speech filter: that filter
                # drops tokens, leaving position gaps a synonym graph cannot be
                # built from (자가판정 -> 자_0, 판정_2).
                "korean_nori_search": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["lowercase", "domain_synonyms", "nori_part_of_speech"],
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
            "source_url": {"type": "keyword", "index": False},
            "published_at": {"type": "date"},
            "effective_from": {"type": "date"},
            "effective_to": {"type": "date"},
            "content_hash": {"type": "keyword", "index": False},
        },
    },
}

HSK_INDEX_BODY = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "korean_nori": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["nori_part_of_speech", "lowercase"],
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

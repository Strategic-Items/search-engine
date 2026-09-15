INDEX_BODY = {
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
            "parent_id": {"type": "keyword"},
            "title": {
                "type": "text", "analyzer": "korean_nori",
                "fields": {"standard": {"type": "text", "analyzer": "standard"}},
            },
            "body": {
                "type": "text", "analyzer": "korean_nori",
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

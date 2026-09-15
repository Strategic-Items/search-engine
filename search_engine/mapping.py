INDEX_BODY = {
    "settings": {
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
            "source_type": {"type": "keyword"},
            "source_url": {"type": "keyword", "index": False},
            "published_at": {"type": "date"},
            "effective_from": {"type": "date"},
            "effective_to": {"type": "date"},
            "content_hash": {"type": "keyword", "index": False},
        },
    },
}

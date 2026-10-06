"""인덱스 정의. 동의어는 검색 시에 확장되므로 문서 자체를 다시 인덱싱하지 않고 사전을 변경할 수 있다."""

# Lucene의 기본값은 VX, VCP 및 VCN을 유지하므로 대화형 종결어는
# "알려줘"와 같이 검색어로 남는다: 알리(VV) + 어(EC) + 주(VX) + 어(EC),
# 그리고 남아 있는 주는 표 주석의 "주 :"로 시작하는 것을 매칭한다.
# 주가 제목에서 드물기 때문에 IDF가 높고, 이는 한 토큰이 모든 내용어에 대한 실제 매칭보다 높은 점수를 얻을 수 있게 하며
# 그 후 비율 컷오프를 매칭한 문서들보다 높게 올린다.
# 보조 동사와 연결사에는 주제가 없다.
KOREAN_POS_FILTER = {
    "type": "nori_part_of_speech",
    # Lucene의 기본 목록, 명시적으로 작성된 것 -- "E"와 "J"는 추상 범주이다
    # 이 버전은 거부하므로 구체적인 종결어미와 조사가 명명된다 --
    # plus VX, VCP 및 VCN.
    "stoptags": [
        # 동사 종결어미와 조사: Lucene의 기본값
        "EC", "EF", "EP", "ETM", "ETN",
        "JC", "JKB", "JKC", "JKG", "JKO", "JKQ", "JKS", "JKV", "JX",
        "IC", "MAG", "MAJ", "MM", "SP", "SSC", "SSO", "SC", "SE",
        "XPN", "XSA", "XSN", "XSV", "UNA", "NA", "VSV",
        # 여기에 추가: 보조동사와 연결사에는 주제가 없다
        "VX", "VCP", "VCN",
    ],
}


def index_body(embedding_dimensions: int) -> dict:
    """핵심 매핑, HNSW 코사인 벡터 인덱스 포함."""
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
# 동의어는 품사 필터 전에 확장된다: 그 필터
# 토큰을 제거하여 위치 갭을 남긴다. 동의어 그래프는 생성할 수 없다
# 따라서 동의어 그래프를 만들 수 없다(자가판정 -> 자_0, 판정_2).
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
            # 제목은 문자 그대로 유지된다: 형태 쿼리가 문서 제목을 거의 명명한다
            # 단어별로, 그리고 그들을 확장하면 정확한 일치가 흐릿한 일치로 바뀐다. 몸체는 어휘 격차를 carrying하므로 확장된다.
            # 몸체는 어휘 격차를 carrying하므로 확장된다.
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
            # 발행일이 아니라 본문 앞머리가 말하는 시점. 부스트 전용이다.
            "period_hint": {"type": "date"},
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


def law_index_body(embedding_dimensions: int) -> dict:
    """법령·고시 카테고리: 문서 매핑에 문서 속성과 조문 경로를 얹는다."""
    body = index_body(embedding_dimensions)
    body["mappings"]["properties"].update({
        # 조문·별표 경로. 짧은 표 행 청크가 어느 별표의 것인지 BM25가 알 수 있게 한다.
        "heading_path": {"type": "text", "analyzer": "korean_nori"},
        "doc_type": {"type": "keyword"},
        "doc_status": {"type": "keyword"},
        "doc_number_norm": {"type": "keyword"},
        "doc_number": {"type": "keyword", "index": False},
        "issuer": {"type": "keyword"},
        "revision_date": {"type": "date"},
        "legal_structure": {"type": "keyword"},
        "chunk_index": {"type": "integer"},
        # 38단계 파인튜닝 SPLADE의 희소 벡터(term → 가중치). 모델이 없으면 비워 둔다.
        "splade": {"type": "rank_features"},
    })
    return body


def callcenter_index_body(embedding_dimensions: int) -> dict:
    """과거 상담에 대한 검색 매핑, 공식 출처와 분리된 상태로."""
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
        # 중첩된 매핑은 향후 피벗형 UI를 위해 유형/값 쌍을 보존한다.
        "entities": {"type": "nested", "properties": {
            "type": {"type": "keyword"},
            "mention": {"type": "text", "analyzer": "korean_nori"},
            "normalized": {"type": "keyword"},
            "seg_ids": {"type": "keyword", "index": False},
        }},
    })
    return body


# 호출자와 테스트를 위해 직접 검사 가능한 기본 매핑을 보존한다.
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

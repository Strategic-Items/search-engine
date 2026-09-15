from opensearchpy import OpenSearch

from search_engine.config import Settings, get_settings


def create_client(settings: Settings | None = None) -> OpenSearch:
    settings = settings or get_settings()
    auth = None
    if settings.opensearch_username or settings.opensearch_password:
        if not (settings.opensearch_username and settings.opensearch_password):
            raise ValueError("OpenSearch username and password must both be set")
        auth = (settings.opensearch_username, settings.opensearch_password)
    return OpenSearch(
        hosts=[settings.opensearch_url],
        http_auth=auth,
        verify_certs=settings.opensearch_verify_certs,
        timeout=10,
        max_retries=2,
        retry_on_timeout=True,
    )

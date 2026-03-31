import pytest
from app.models.settings import FilterConfig
from app.services.scraper import _matches_filters


def test_keyword_match():
    filters = FilterConfig(keywords=["Python"], roles=[], exclude_keywords=[])
    assert _matches_filters("Python developer role", filters) is True


def test_keyword_no_match():
    filters = FilterConfig(keywords=["Python"], roles=[], exclude_keywords=[])
    assert _matches_filters("Java Spring Boot developer", filters) is False


def test_exclude_keyword_blocks():
    filters = FilterConfig(keywords=[], roles=[], exclude_keywords=["10+ years"])
    assert _matches_filters("Senior engineer, 10+ years required", filters) is False


def test_no_filters_passes_all():
    filters = FilterConfig(keywords=[], roles=[], exclude_keywords=[])
    assert _matches_filters("Any job title or description", filters) is True


def test_role_filter():
    filters = FilterConfig(keywords=[], roles=["Software Engineer"], exclude_keywords=[])
    assert _matches_filters("Software Engineer at Acme Corp", filters) is True
    assert _matches_filters("Marketing Manager at Acme Corp", filters) is False

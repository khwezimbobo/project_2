from rest_framework.pagination import PageNumberPagination


# --------------------------------------------------
# API PAGINATION
# --------------------------------------------------
class StandardPagination(PageNumberPagination):
    """20 results per page; clients may ask for fewer or more with ?page_size=."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

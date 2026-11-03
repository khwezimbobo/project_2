from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """20 records per page on every list endpoint (BRD 8.2).

    Responses look like: {"count": 25, "next": "...?page=2", "previous": null, "results": [...]}
    """

    page_size = 20
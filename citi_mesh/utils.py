from datetime import datetime


def json_serializer(o):
    if isinstance(o, datetime):
        return o.isoformat()
    else:
        return o

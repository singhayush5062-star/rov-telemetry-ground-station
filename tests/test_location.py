from gui.location import parse_origin_arg, parse_ip_geolocation


def test_parse_origin_arg():
    assert parse_origin_arg("28.6654,77.4391") == (28.6654, 77.4391)
    assert parse_origin_arg(" -33.9, 151.2 ") == (-33.9, 151.2)
    assert parse_origin_arg(None) is None
    assert parse_origin_arg("") is None
    assert parse_origin_arg("abc") is None
    assert parse_origin_arg("95,10") is None          # out of range
    assert parse_origin_arg("10,200") is None


def test_parse_ipapi_payload():
    lat, lon, place = parse_ip_geolocation(b'{"latitude": 28.58, "longitude": 77.33, "city": "Noida", "country_code": "IN", "country": "IN", "country_name": "India"}')
    assert (lat, lon) == (28.58, 77.33) and place == "Noida, India"


def test_parse_ipinfo_payload():
    lat, lon, place = parse_ip_geolocation('{"loc": "28.6654,77.4391", "city": "Ghaziabad", "country": "IN"}')
    assert (lat, lon) == (28.6654, 77.4391) and place == "Ghaziabad, IN"


def test_parse_ip_geolocation_rejects_garbage():
    assert parse_ip_geolocation(b"") is None
    assert parse_ip_geolocation(b"not json") is None
    assert parse_ip_geolocation(b'{"error": true}') is None
    assert parse_ip_geolocation(b'{"loc": "x,y"}') is None

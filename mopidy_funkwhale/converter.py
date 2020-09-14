from mopidy import models
from . import uri

def json_to_track_ref(json):
    return models.Ref.track(uri=uri.get_track_uri(json["id"]), name=json["title"])

def json_to_track(json):
    if len(json["uploads"]):
        upload = json["uploads"][0]
    else:
        upload = {"duration": 0, "bitrate": 0}
    return models.Track(
        uri = uri.get_track_uri(json["id"]),
        name = json["title"],
        artists = [json_to_artist(json["artist"])],
        album = json_to_album(json["album"]),
        composers = [],
        performers = [],
        genre = str(json["tags"]),
        track_no = json.get("position"),
        disc_no = json.get("disc_number"),
        date = json["album"]["release_date"],
        length = upload.get("duration", 0)*1000,
        bitrate = int(upload.get("bitrate", 0)/1000),
        comment = "",
        musicbrainz_id = json["mbid"]
    )

def json_to_album(json):
    return models.Album(
        uri = uri.get_album_uri(json["id"]),
        name = json["title"],
        artists = [json_to_artist(json["artist"]), ],
        num_tracks = None,
        num_discs = None,
        date = json["release_date"],
        musicbrainz_id = json["mbid"],
    )

def json_to_artist(json):
    return models.Artist(
        uri = uri.get_artist_uri(json["id"]),
        name = json["name"],
        sortname = json["name"],
        musicbrainz_id = json["mbid"],
    )


def json_to_image(json):
    return models.Image(
        uri=json
    )



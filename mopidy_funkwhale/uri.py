PREFIX = "funkwhale"

PLAYLIST = "playlist"
TRACK = "track"
ALBUM = "album"
ARTIST = "artist"
PATH = "directory"

def get_type(uri):
    return uri.split(":")[1]

def get_uri(type, id):
    return f"{PREFIX}:{type}:{id}"

def get_id(uri):
    return uri.split(":")[2]

def get_track_uri(track_id):
    return get_uri(TRACK, track_id)

def get_track_id(uri):
    return get_id(uri)

def get_playlist_uri(playlist_id):
    return get_uri(PLAYLIST, playlist_id)

def get_playlist_id(uri):
    return get_id(uri)

def get_album_uri(album_id):
    return get_uri(ALBUM, album_id)

def get_album_id(uri):
    return get_id(uri)

def get_artist_uri(artist_id):
    return get_uri(ARTIST, artist_id)

def get_artist_id(uri):
    return get_id(uri)

def get_path(uri):
    return get_id(uri)

def get_path_uri(path):
    return get_uri(PATH, path)

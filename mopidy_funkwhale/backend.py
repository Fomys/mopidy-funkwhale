import logging

import pykka
import requests
import requests_oauthlib
import os
import datetime
import json

from mopidy import httpclient, exceptions
from mopidy import backend, models
from . import __version__, uri, converter


REQUIRED_SCOPES = ["read", "write"] #"read:libraries", "read:favorites", "read:playlists", "write:playlists"]


class SessionWithUrlBase(requests.Session):
    # In Python 3 you could place `url_base` after `*args`, but not in Python 2.
    def __init__(self, url_base=None, *args, **kwargs):
        super(SessionWithUrlBase, self).__init__(*args, **kwargs)
        self.url_base = url_base

    def request(self, method, url, **kwargs):
        # Next line of code is here for example purposes only.
        # You really shouldn't just use string concatenation here,
        # take a look at urllib.parse.urljoin instead.
        if url.startswith("http://") or url.startswith("https://"):
            modified_url = url
        else:
            modified_url = self.url_base + url

        return super(SessionWithUrlBase, self).request(method, modified_url, **kwargs)

class OAuth2Session(SessionWithUrlBase, requests_oauthlib.OAuth2Session):
    pass

logger = logging.getLogger(__name__)


class FunkwhalePlaybackProvider(backend.PlaybackProvider):
    def translate_uri(self, p_uri):
        id = uri.get_track_id(p_uri)
        track = self.backend.client.get_track(id)

        if track is None:
            return None
        url = track["listen_url"]

        if url.startswith("/"):
            url = self.backend.config["funkwhale"]["url"] + url
        url += "?token=" + self.backend.client.oauth_token["access_token"]
        return url


class FunkwhalePlaylistProvider(backend.PlaylistsProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def as_list(self):
        json = self.backend.client.get_playlists()
        playlists = []
        if json is not None:
            for playlist in json["results"]:
                playlists.append(
                    models.Ref.playlist(
                        uri = uri.get_playlist_uri(playlist["id"]),
                        name = playlist["name"]
                    )
                )
        return playlists

    def create(self, name):
        json = self.backend.client.create_playlist(name)
        if json is not None:
            id = json["id"]
            return self.lookup(uri.get_playlist_uri(id))
        return None

    def save(self, playlist):
        # Sauvegarder aussi les musiques
        json = self.backend.client.update_playlist(uri.get_playlist_id(playlist.uri), playlist.name)
        if json is not None:
            id = json["id"]
            tracks = [uri.get_track_id(track.uri) for track in playlist.tracks]
            self.backend.client.clear_playlist(id)
            self.backend.client.add_tracks_playlist(id, tracks)
            return self.lookup(uri.get_playlist_uri(id))
        return None

    def delete(self, p_uri):
        return self.backend.client.delete_playlist(uri.get_playlist_id(p_uri))

    def lookup(self, p_uri):
        id = uri.get_playlist_id(p_uri)
        json = self.backend.client.get_playlists(id)
        name = None
        lenght = None
        tracks = []
        last_modified = None
        if json is not None:
            # .replace: fix pour fromisoformat qui ne supporte pas le Z
            last_modified = int(datetime.datetime.fromisoformat(json["modification_date"].replace('Z', '+00:00')).timestamp())
            name = json["name"]
            lenght = json["tracks_count"]
            json = self.backend.client.get_playlists_tracks(id)
            if json is not None:
                for track in json["results"]:
                    tracks.append(
                        converter.json_to_track(track["track"])
                    )
        return models.Playlist(
            uri=p_uri,
            name=name,
            tracks=tracks,
            last_modified=last_modified
        )

    def get_items(self, p_uri):
        id = uri.get_playlist_id(p_uri)
        json = self.backend.client.get_playlists_tracks(id)
        if json is not None:
            tracks = []
            for track in json["results"]:
                tracks.append(
                    models.Ref.track(uri=uri.get_track_uri(track["track"]["id"]), name=track["track"]["title"])
                )
            return tracks
        return None

def simplify_search_query(query):

    if isinstance(query, dict):
        r = []
        for v in query.values():
            if isinstance(v, list):
                r.extend(v)
            else:
                r.append(v)
        return " ".join(r)
    if isinstance(query, list):
        return " ".join(query)
    else:
        return query


class FunkwhaleLibraryProvider(backend.LibraryProvider):
    root_directory = models.Ref.directory(uri=uri.get_path_uri("/"), name="Funkwhale")

    def search(self, query=None, uris=None, exact=False):
        # TODO Support exact search
        if not query:
            return

        else:
            search_query = simplify_search_query(query)
            logger.info("Searching Funkwhale for: %s", search_query)
            raw_results = self.backend.client.search(search_query)
            if raw_results is None:
                return None
            artists = [converter.json_to_artist(row) for row in raw_results["artists"]]
            albums = [converter.json_to_album(row) for row in raw_results["albums"]]
            tracks = [] #[converter.json_to_track(row) for row in raw_results["tracks"]]
            for track in raw_results["tracks"]:
                tracks.append(converter.json_to_track(track))
            return models.SearchResult(
                uri="funkwhale:search", tracks=tracks, albums=albums, artists=artists
            )

    def lookup(self, p_uri):
        tracks = []
        id = uri.get_track_id(p_uri)
        json = self.backend.client.get_track(id)
        if json is not None:
            tracks.append(converter.json_to_track(json))
        return tracks

    def browse(self, p_uri):
        if uri.get_type(p_uri) == uri.PATH:
            path = uri.get_path(p_uri)
            if path == "/":
                return self._get_root_dirs()
            if path.startswith("/albums"):
                return self._get_albums()
            if path.startswith("/artists"):
                return self._get_artists()
            if path.startswith("/favorites"):
                return self._get_favorites()
        if uri.get_type(p_uri) == uri.ALBUM:
            return self._get_album(p_uri)
        if uri.get_type(p_uri) == uri.ARTIST:
            return self._get_artist(p_uri)
        return []

    def _get_root_dirs(self):
        return [
            models.Ref.directory(uri='funkwhale:directory:/albums', name='Albums'),
            models.Ref.directory(uri='funkwhale:directory:/artists', name='Artists'),
            models.Ref.directory(uri='funkwhale:directory:/favorites', name='Favorites'),
        ]

    def _get_favorites(self):
        json = self.backend.client.get_favorites()
        tracks = []
        if json is not None:
            for track in json:
                tracks.append(models.Ref.track(uri=uri.get_track_uri(track["id"]), name=track["title"]))
        return tracks

    def _get_album(self, p_uri):
        json = self.backend.client.get_album_tracks(uri.get_id(p_uri))
        if json is not None:
            return [converter.json_to_track_ref(track) for track in json]
        return []

    def _get_albums(self):
        json = self.backend.client.get_albums()
        albums = []
        if json is not None:
            for album in json:
                albums.append(models.Ref.album(uri=uri.get_album_uri(album["id"]), name=album["title"]))
        return albums

    def _get_artists(self):
        json = self.backend.client.get_artists()
        artists = []
        if json is not None:
            for artist in json:
                artists.append(models.Ref.artist(uri=uri.get_artist_uri(artist["id"]), name=artist["name"]))
        return artists

    def _get_artist(self, p_uri):
        json = self.backend.client.get_artist_tracks(uri.get_id(p_uri))
        if json is not None:
            return [converter.json_to_track_ref(track) for track in json]
        return []

    def get_images(self, p_uris):
        images = dict()
        for p_uri in p_uris:
            id = uri.get_track_id(p_uri)
            if uri.get_type(p_uri) == uri.ALBUM:
                json = self.backend.client.get_album(id)
                if json is not None:
                    images.update({p_uri:[
                        converter.json_to_image(json["cover"]["urls"]["original"])
                    ]})
        return images


class APIClient:
    def __init__(self, config):
        self.config = config
        self.jwt_token = None
        self.oauth_token = get_token(config)

        base_url = config["funkwhale"]["url"]

        if not base_url.endswith("/api/v1/"):
           base_url += "/api/v1/"
        proxy = httpclient.format_proxy(config["proxy"])
        full_user_agent = httpclient.format_user_agent("%s/%s" % ("Mopidy-Funkwhale", __version__))

        self.session = OAuth2Session(
            url_base = base_url,
            client_id=self.config["funkwhale"]["client_id"],
            token=self.oauth_token,
            auto_refresh_url=config["funkwhale"]["url"]
                + config["funkwhale"].get("token_endpoint")
                or "/api/v1/oauth/token/",
            auto_refresh_kwargs={
                "client_id": self.config["funkwhale"]["client_id"],
                "client_secret": self.config["funkwhale"]["client_secret"],
            },
            token_updater=self.refresh_token,

        )

        self.session.proxies.update({"http": proxy, "https": proxy})
        self.session.headers.update({"user-agent": full_user_agent})

        self.session.verify = config["funkwhale"].get("verify_cert", True)

    def refresh_token(self, token):
        self.oauth_token = token
        set_token(token, self.config)

    def get_favorites(self):
        response = self.session.get("tracks/?favorites=true&ordering=-creation_date&page=1&page_size=50")
        results = []
        results.extend(response.json()["results"])
        while response and response.json()["next"] is not None:
            response = self.session.get(response.json()["next"])
            results.extend(response.json()["results"])
        return results

    def get_playlists(self, id=None):
        if id is None:
            response = self.session.get("playlists/")
            if response:
                return response.json()
        if id:
            response = self.session.get(f"playlists/{id}")
            if response:
                return response.json()
        return None

    def get_playlists_tracks(self, id):
        response = self.session.get(f"playlists/{id}/tracks")
        if response:
            return response.json()

    def get_track(self, id):
        response = self.session.get(f"tracks/{id}")
        if response:
            return response.json()

    def get_albums(self):
        response = self.session.get("albums/?ordering=title&page=1&page_size=50&scope=all")
        results = []
        results.extend(response.json()["results"])
        while response and response.json()["next"] is not None:
            response = self.session.get(response.json()["next"])
            results.extend(response.json()["results"])
        return results

    def get_artists(self):
        response = self.session.get("artists/?ordering=name&page=1&page_size=50&scope=all")
        results = []
        results.extend(response.json()["results"])
        while response and response.json()["next"] is not None:
            response = self.session.get(response.json()["next"])
            results.extend(response.json()["results"])
        return results

    def get_album_tracks(self, id):
        response = self.session.get(f"tracks/?page_size=50&album={id}&ordering=disc_number,position")
        results = []
        results.extend(response.json()["results"])
        while response and response.json()["next"] is not None:
            response = self.session.get(response.json()["next"])
            results.extend(response.json()["results"])
        return results

    def get_artist_tracks(self, id):
        response = self.session.get(f"tracks/?page_size=50&artist={id}&ordering=title")
        results = []
        results.extend(response.json()["results"])
        while response and response.json()["next"] is not None:
            response = self.session.get(response.json()["next"])
            results.extend(response.json()["results"])
        return results

    def get_album(self, id):
        response = self.session.get(f"albums/{id}")
        if response:
            return response.json()

    def create_playlist(self, name):
        response = self.session.post("playlists/", data = {"name": name})
        if response:
            return response.json()

    def update_playlist(self, id, name):
        response = self.session.patch(f"playlists/{id}", data={"name": name})
        if response:
            return response.json()

    def delete_playlist(self, id):
        return bool(self.session.delete(f"playlists/{id}"))

    def clear_playlist(self, id):
        return bool(self.session.delete(f"playlists/{id}/clear"))

    def add_tracks_playlist(self, id, tracks):
        return bool(self.session.post(f"playlists/{id}/add", data={"tracks": tracks, "allow_duplicates": True}))

    def search(self, query):
        response = self.session.get("search", params={"query": query})
        if response:
            return response.json()

class FunkwhaleBackend(pykka.ThreadingActor, backend.Backend):
    uri_schemes = ["funkwhale"]

    def __init__(self, config, audio):
        super().__init__()
        self.config = config
        self.client = APIClient(config)
        self.library = FunkwhaleLibraryProvider(backend=self)
        self.playback = FunkwhalePlaybackProvider(audio=audio, backend=self)
        self.playlists = FunkwhalePlaylistProvider(backend=self)

    def on_start(self):
        if self.config["funkwhale"]["client_id"]:
            logger.info('Using OAuth2 connection"')
        else:
            logger.info('Using "%s" anonymously', self.config["funkwhale"]["url"])

def get_token(config):
    import mopidy_funkwhale

    data_dir = mopidy_funkwhale.Extension.get_data_dir(config)
    try:
        with open(os.path.join(data_dir, "token"), "r") as f:
            raw = f.read()
    except IOError:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        logger.error("Cannot decode token data, you may need to relogin")


def set_token(token_data, config):
    import mopidy_funkwhale

    data_dir = mopidy_funkwhale.Extension.get_data_dir(config)
    print(data_dir)
    content = json.dumps(token_data)
    with open(os.path.join(data_dir, "token"), "w") as f:
        f.write(content)

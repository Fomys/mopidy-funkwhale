from mopidy import commands, exceptions

import requests_oauthlib

from . import backend as client


def urlencode(data):
    try:
        import urllib.parse

        return urllib.parse.urlencode(data)
    except ImportError:
        # python 2
        import urllib

        return urllib.urlencode(data)


class FunkwhaleCommand(commands.Command):
    def __init__(self):
        super(FunkwhaleCommand, self).__init__()
        self.add_child("login", LoginCommand())


class LoginCommand(commands.Command):
    help = (
        "Display authorization URL and instructions to connect with Funkwhale server."
    )

    def run(self, args, config):
        import mopidy_funkwhale

        url = config["funkwhale"]["url"]
        authorize_endpoint = (
            config["funkwhale"].get("authorize_endpoint") or "/authorize"
        )
        token_endpoint = (
            config["funkwhale"].get("token_endpoint") or "/api/v1/oauth/token/"
        )
        client_id = config["funkwhale"]["client_id"]
        client_secret = config["funkwhale"]["client_secret"]
        if not client_id or not client_secret:
            params = {
                "name": "Mopidy-Funkwhale",
                "scopes": " ".join(client.REQUIRED_SCOPES),
                "redirect_uris": "urn:ietf:wg:oauth:2.0:oob",
            }
            app_url = url + "/settings/applications/new?" + urlencode(params)
            print(
                "\nMissing client_id or client_secret! To connect to your Funkwhale account:\n\n"
                "1. Create an app by visiting {}"
                "\n2. Ensure the created app has 'urn:ietf:wg:oauth:2.0:oob' as "
                "redirect URI, and the following scopes: {}"
                "\n3. Update the client_id and client_secret values in the [funkwhale] section of your mopidy configuration, to match the values of the created application"
                "\n4. Relaunch this command".format(
                    app_url, ", ".join(client.REQUIRED_SCOPES)
                )
            )
            return 1

        oauth = requests_oauthlib.OAuth2Session(
            client_id,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
            scope=client.REQUIRED_SCOPES,
        )
        oauth.verify = config["funkwhale"].get("verify_cert", True)
        authorize_url, state = oauth.authorization_url(url + authorize_endpoint)
        print(
            "\nTo login:\n\n"
            "1. Visit the following URL: {}"
            "\n2. Authorize the application"
            "\n3. Copy-paste the token you obtained and press enter".format(
                authorize_url
            )
        )

        prompt = "\nEnter the token:"

        authorization_code = input(prompt)
        token = oauth.fetch_token(
            url + token_endpoint,
            code=authorization_code,
            client_id=client_id,
            client_secret=client_secret,
        )
        client.set_token(token, config)
        print("Login successful!")
        return 0

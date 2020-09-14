import logging
import os

import mopidy
from mopidy import config, ext


logger = logging.getLogger(__name__)

__version__ = "0.0.1"

class Extension(ext.Extension):

    dist_name = "Mopidy-Funkwhale"
    ext_name = "funkwhale"
    version = __version__

    def get_default_config(self):
        conf_file = os.path.join(os.path.dirname(__file__), "ext.conf")
        return config.read(conf_file)

    def get_config_schema(self):
        schema = super(Extension, self).get_config_schema()
        schema["url"] = mopidy.config.String()
        schema["authorization_endpoint"] = mopidy.config.String(optional=True)
        schema["token_endpoint"] = mopidy.config.String(optional=True)
        schema["client_secret"] = mopidy.config.String(optional=True)
        schema["client_id"] = mopidy.config.String(optional=True)

        schema["cache_duration"] = mopidy.config.Integer(optional=True)
        schema["verify_cert"] = mopidy.config.Boolean(optional=True)
        return schema

    def setup(self, registry):
        from .backend import FunkwhaleBackend

        registry.add("backend", FunkwhaleBackend)

    def validate_config(self, config):
        if not config.getboolean("funkwhale", "enabled"):
            return
        username = config.getstring("funkwhale", "username")
        password = config.getstring("funkwhale", "password")
        if any([username, password]) and not all([username, password]):
            raise mopidy.ext.ExtensionError(
                "You need to provide username and password to authenticate with the funkwhale backend"
            )

    def get_command(self):
        from . import commands

        return commands.FunkwhaleCommand()

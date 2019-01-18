import os
import json
import click
from urllib.parse import urlparse

from . import cli
from meltano.core.plugin import PluginType
from meltano.core.project import Project
from meltano.core.plugin_discovery_service import (
    PluginDiscoveryService,
    DiscoveryInvalidError,
)


@cli.command()
@click.argument(
    "plugin_type",
    type=click.Choice(
        [
            PluginType.EXTRACTORS,
            PluginType.LOADERS,
            PluginType.TRANSFORMERS,
            PluginType.TRANSFORMS,
            PluginType.ALL,
        ]
    ),
)
def discover(plugin_type):
    discover_service = PluginDiscoveryService(Project.find())
    try:
        discovery_dict = discover_service.discover(plugin_type)
        for key, value in discovery_dict.items():
            click.secho(key, fg="green")
            click.echo(value)
    except Exception as e:
        click.secho("Cannot list available plugins.", fg="red")
        raise click.ClickException(str(e))

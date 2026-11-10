"""Native Hermes plugin. Registration performs no IO and starts no background work."""
from .bridge.api import DEFINITIONS, TOOLSET, handler_for, schema


def register(ctx):
    for name in DEFINITIONS:
        ctx.register_tool(name=name, toolset=TOOLSET, schema=schema(name), handler=handler_for(name))

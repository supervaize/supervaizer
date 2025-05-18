# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import sys

from art import text2art
from rich import box, print
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from supervaizer.__version__ import VERSION

console = Console()


def make_layout() -> Layout:
    """Define the layout."""
    layout = Layout(name="root")

    layout.split(
        Layout(name="header", size=10),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=7),
    )
    layout["main"].split_row(
        Layout(name="side"),
        Layout(name="body", ratio=2, minimum_size=100),
    )
    return layout


def make_documentation_message(server_url: str) -> Panel:
    """Some example content."""
    sponsor_message = Table.grid(padding=1)
    sponsor_message.add_column(style="green", justify="right")
    sponsor_message.add_column(no_wrap=True)
    sponsor_message.add_row(
        "Integration documentation",
        "[u blue link=https://supervaize.com/docs/integration]https://supervaize.com/docs/integration[/]",
    )
    sponsor_message.add_row()
    sponsor_message.add_row(
        "Swagger",
        f"[u blue link={server_url}/docs]{server_url}/docs[/]",
    )
    sponsor_message.add_row(
        "Redoc",
        f"[u blue link={server_url}/redoc]{server_url}/redoc[/]",
    )
    sponsor_message.add_row(
        "API",
        f"[u blue link={server_url}/api]{server_url}/api[/]",
    )

    message = Table.grid(padding=1)
    message.add_column()
    message.add_column(no_wrap=True)
    message.add_row(sponsor_message)

    message_panel = Panel(
        Align.center(
            Group("\n", Align.center(sponsor_message)),
            vertical="middle",
        ),
        box=box.ROUNDED,
        padding=(1, 2),
        title="[b red]Check Supervaize documentation",
        border_style="bright_blue",
    )
    return message_panel


class Header:
    def __rich__(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="right")
        logo = text2art("Supervaize Control")
        grid.add_row(logo, f"[b]v{VERSION}[/]")
        return Panel(grid, border_style="blue")


def make_syntax() -> Panel:
    """Create a syntax-highlighted code panel."""
    code = """\
from supervaizer Server, Account, Agent
sv_account = Account(
    name="CUSTOMERFIRST",
    id="xxxxxxxxxxxx",
    api_key=os.getenv("SUPERVAIZE_API_KEY"),
    api_url=os.getenv("SUPERVAIZE_API_URL"),
    )

job_start = AgentMethod(
    name="job_start",
    method="control.job_start",
    params={"action": "run"},
    description="Start the job",
    )
agent = Agent(
    name="my_agent",
    account=sv_account,
    method=job_start_method,
)
server = Server()
server.launch()
    """
    syntax = Syntax(code, "python", line_numbers=True)
    panel = Panel(syntax, border_style="green", title="Sample integration code")
    return panel


def make_footer(status_message: str) -> Panel:
    """Create a footer panel with status message."""
    return Panel(status_message, border_style="green")


def display_instructions(server_url: str, status_message: str) -> None:
    """Display the full instructions layout.

    Args:
        server_url: The URL where the server is running
        status_message: Status message to display in footer
    """
    layout = make_layout()
    layout["header"].update(Header())
    layout["body"].update(make_documentation_message(server_url))
    layout["side"].update(make_syntax())
    layout["footer"].update(make_footer(status_message))

    print(layout)
    sys.exit(0)  # This function never returns normally


if __name__ == "__main__":
    display_instructions(
        "http://127.0.0.1:8000", "Starting server on http://127.0.0.1:8000"
    )

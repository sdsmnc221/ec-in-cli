"""
civique.sync — Sync toggle UI and syncKey management.
Only accessible from the startup/home screen, never mid-session.

State stored in stats dict:
  stats["sync_enabled"]  : bool
  stats["sync_key"]      : str | None
"""

import uuid
import sys

from rich.panel import Panel
from rich.rule import Rule

from .ui import console, TRICOLOR, getch


# ─── Accessors ────────────────────────────────────────────────────────────────

def is_enabled(stats: dict) -> bool:
    return bool(stats.get("sync_enabled", False))


def get_key(stats: dict) -> str | None:
    return stats.get("sync_key") or None


def set_key(stats: dict, key: str):
    stats["sync_key"] = key.strip()


def set_enabled(stats: dict, enabled: bool):
    stats["sync_enabled"] = enabled


# ─── Key prompt ───────────────────────────────────────────────────────────────

def _key_prompt(stats: dict, title: str = "CLÉ DE SYNCHRONISATION") -> bool:
    """
    Prompt for a sync key: paste or generate.
    Returns True if a key was set, False if user cancelled.
    """
    while True:
        console.clear()
        console.print(Panel(
            f"[bold {TRICOLOR['blue']}]{title}[/]",
            border_style=TRICOLOR["blue"], padding=(0, 2)
        ))
        console.print()
        console.print(
            f"  La clé identifie vos stats sur tous vos appareils.\n"
            f"  [dim]Utilisez la même clé que dans votre application mobile.[/]"
        )
        console.print()
        console.print(f"  [bold white][P][/] [dim]Coller une clé existante[/]")
        console.print(f"  [bold white][G][/] [dim]Générer une nouvelle clé (UUID)[/]")
        console.print(f"  [bold white][←][/] [dim]Annuler[/]")
        console.print()

        key = getch()
        k   = key.lower()

        if k == 'p':
            console.print(f"  [bold white]Collez votre clé :[/] ", end="")
            try:
                raw = input().strip()
                if raw:
                    set_key(stats, raw)
                    _confirm_key(stats)
                    return True
                else:
                    console.print("  [red]Clé vide — réessayez.[/]")
                    import time; time.sleep(0.8)
            except EOFError:
                return False

        elif k == 'g':
            new_key = str(uuid.uuid4())
            set_key(stats, new_key)
            console.clear()
            console.print(Panel(
                f"[bold {TRICOLOR['gold']}]CLÉ GÉNÉRÉE[/]",
                border_style=TRICOLOR["gold"], padding=(0, 2)
            ))
            console.print()
            console.print(f"  [bold white]{new_key}[/]")
            console.print()
            console.print(
                f"  [dim]Copiez cette clé dans votre application mobile\n"
                f"  pour synchroniser vos stats entre appareils.[/]"
            )
            console.print()
            console.print(f"  [dim]Appuyez sur [white]Entrée[/] pour continuer…[/]")
            input()
            return True

        elif key in ('LEFT', '\x1b', 'q', 'Q', '\x03'):
            return False


def _confirm_key(stats: dict):
    """Brief confirmation flash after key is set."""
    key = get_key(stats)
    short = f"{key[:8]}…{key[-4:]}" if key and len(key) > 16 else key
    console.print()
    console.print(
        f"  [{TRICOLOR['green']}]✓[/] Clé enregistrée : "
        f"[bold white]{short}[/]"
    )
    console.print(f"  [dim]Appuyez sur [white]Entrée[/] pour continuer…[/]")
    input()


# ─── Toggle screen ────────────────────────────────────────────────────────────

def toggle_screen(stats: dict) -> bool:
    """
    Main sync management screen — called from startup home screen via [S].
    Returns True if stats were mutated (caller should save).

    States:
      sync OFF, no key   → offer to turn ON (prompts for key)
      sync OFF, has key  → show current key, offer ON or change key
      sync ON            → show status, offer OFF or change key
    """
    currently_on = is_enabled(stats)
    current_key  = get_key(stats)
    changed      = False

    while True:
        console.clear()
        console.print(Panel(
            f"[bold {TRICOLOR['blue']}]SYNCHRONISATION CONVEX[/]",
            border_style=TRICOLOR["blue"], padding=(0, 2)
        ))
        console.print()

        # Status line
        if currently_on:
            short = _short_key(current_key)
            console.print(
                f"  Statut : [{TRICOLOR['green']}]● ACTIVÉE[/]  "
                f"[dim]clé :[/] [bold white]{short}[/]"
            )
        else:
            console.print(f"  Statut : [dim]○ DÉSACTIVÉE[/]")
            if current_key:
                short = _short_key(current_key)
                console.print(f"  [dim]Dernière clé : {short}[/]")

        console.print()
        console.print(Rule(style="dim"))
        console.print()

        # Options
        if currently_on:
            console.print(f"  [bold white][O][/] [dim]Désactiver la synchronisation[/]")
            console.print(f"  [bold white][C][/] [dim]Changer de clé[/]")
        else:
            console.print(f"  [bold white][O][/] [dim]Activer la synchronisation[/]")
            if current_key:
                console.print(f"  [bold white][C][/] [dim]Changer de clé[/]")

        console.print(f"  [bold white][←][/] [dim]Retour[/]")
        console.print()

        key = getch()
        k   = key.lower()

        # Toggle ON/OFF
        if k == 'o':
            if currently_on:
                # Turn off
                set_enabled(stats, False)
                currently_on = False
                changed      = True
                console.print(f"\n  [dim]Synchronisation désactivée.[/]")
                import time; time.sleep(0.8)

            else:
                # Turn on — need a key
                if not current_key:
                    got_key = _key_prompt(stats)
                    if not got_key:
                        continue
                    current_key = get_key(stats)
                    changed     = True

                set_enabled(stats, True)
                currently_on = True
                changed      = True
                console.print(
                    f"\n  [{TRICOLOR['green']}]✓[/] "
                    f"Synchronisation activée."
                )
                import time; time.sleep(0.8)

        # Change key
        elif k == 'c' and current_key:
            got_key = _key_prompt(stats, title="CHANGER DE CLÉ")
            if got_key:
                current_key = get_key(stats)
                changed     = True

        # Back
        elif key in ('LEFT', '\x1b', '\r', '\n', 'q', 'Q', '\x03'):
            break

    return changed


# ─── Startup status line (shown on home screen) ───────────────────────────────

def status_line(stats: dict) -> str:
    """One-line sync status for the startup screen."""
    if is_enabled(stats):
        short = _short_key(get_key(stats))
        return (
            f"  [dim]Sync :[/] [{TRICOLOR['green']}]● activée[/]  "
            f"[dim]clé {short}[/]  "
            f"[dim]— [white][S][/] pour gérer[/]"
        )
    else:
        return (
            f"  [dim]Sync :[/] [dim]○ désactivée[/]  "
            f"[dim]— [white][S][/] pour activer[/]"
        )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _short_key(key: str | None) -> str:
    if not key:
        return "[dim]aucune[/]"
    if len(key) > 16:
        return f"{key[:8]}…{key[-4:]}"
    return key

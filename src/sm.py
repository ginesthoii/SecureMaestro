#!/usr/bin/env python3
import typer
from rich import print
from securemaestro.looper import youtube_practice_loop

app = typer.Typer(help="SecureMaestro CLI")

@app.command()
def looper(
    url: str = typer.Argument(..., help="YouTube URL"),
    start: float = typer.Option(0.0, help="Start time in seconds"),
    end: float = typer.Option(15.0, help="End time in seconds"),
    speed: float = typer.Option(0.7, help="Playback speed (0.5-2.0). Ex: 0.5, 0.7, 0.9"),
    repeats: int = typer.Option(5, help="How many times to repeat the section"),
    out: str = typer.Option("outputs/looped.wav", help="Output file path (.wav/.mp3)"),
    max_download_sec: int = typer.Option(1200, help="Max full video length allowed (sec)")
):
    """
    Download audio from YouTube, cut [start,end], apply speed, and repeat N times.
    """
    try:
        path = youtube_practice_loop(
            url=url,
            start_sec=start,
            end_sec=end,
            speed=speed,
            repeats=repeats,
            output_path=out,
            max_full_length_sec=max_download_sec
        )
        print(f"[bold green]Done![/bold green] Wrote: {path}")
    except Exception as e:
        print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1)

if __name__ == "__main__":
    app()
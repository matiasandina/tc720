import argparse
from collections import deque
from rich.console import Console

from .serial_utils import setup_connection
from .controller import TC720
from .program_utils import load_program
from .ramp_runner import monitor_ramp_soak

def test_dry_run_program(program_path: str):
    program = load_program(program_path)
    console = Console()
    port = setup_connection()
    if not port:
        console.print("[bold red]No serial port found. Please connect the controller and try again.[/bold red]")
        return

    controller = TC720(port, default_temp=22)
    controller.set_active()
    controller.set_mode(1)
    controller.output_enable(True)
    print("[yellow]Clearing old program...[/yellow]")
    controller.clear_sequence()

    console.print("[yellow]Dry-running program with constant temperature and 5s ramps/soaks...[/yellow]")

    for step in program['locations']:
        controller.set_single_sequence(
            location=step['location'],
            temp=controller.default_temp,
            ramp_time=5,
            soak_time=5,
            repeats=step.get('repeats', 0),
            go_to=step.get('go_to')
        )

    data_buffer = deque(maxlen=300)
    controller.start_soak()
    monitor_ramp_soak(controller, data_buffer, output_filename="dry_run_output.csv")

def cli_entry():
    parser = argparse.ArgumentParser(description="Dry-run a TC720 program with constant temperature and fast timing.")
    parser.add_argument("program_yaml", help="Path to the program YAML file")
    args = parser.parse_args()
    test_dry_run_program(args.program_yaml)

if __name__ == "__main__":
    cli_entry()
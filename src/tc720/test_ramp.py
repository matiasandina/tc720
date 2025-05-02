from tc720.ramp_runner import monitor_ramp_soak
from .serial_utils import setup_connection
from .controller import TC720
from rich import print
from collections import deque

def test_simple_repeat(controller, data_buffer: list, repeats: int = 2):
    print("[bold cyan]Running simple test ramp[/bold cyan]")
    controller.set_active()
    controller.set_mode(1)
    controller.output_enable(True)

    print("[yellow]Clearing old program...[/yellow]")
    controller.clear_sequence()

    print("[yellow]Writing new sequence...[/yellow]")
    controller.set_single_sequence(location=1, temp=22, ramp_time=60, soak_time=30, repeats=1, go_to=None)
    controller.set_single_sequence(location=2, temp=21, ramp_time=60, soak_time=30, repeats=1, go_to=None)
    controller.set_single_sequence(location=3, temp=22, ramp_time=60, soak_time=30, repeats=repeats, go_to=1)

    print("[green]Program loaded:[/green]")
    print("1: 22°C → soak 30s, go_to=2")
    print("2: 21°C → soak 30s, go_to=3")
    print(f"3: 22°C → soak 30s, repeats={repeats}, go_to=1")
    print("[bold cyan]Press ENTER to begin the soak sequence...[/bold cyan]")
    input("")

    controller.start_soak()
    monitor_ramp_soak(controller, data_buffer, output_filename="test_ramp_output.csv")


def cli_entry():
    port = setup_connection()
    if not port:
        print("[bold red]No serial port found. Please connect the controller and try again.[/bold red]")
        return
    # just in case initialize with default 22, which shouldn't be too far away from room temp
    controller = TC720(port, default_temp = 22)
    data_buffer = deque(maxlen=300)
    test_simple_repeat(controller, data_buffer, repeats=2)

if __name__ == "__main__":
    cli_entry()
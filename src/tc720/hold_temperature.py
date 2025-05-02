import time
from rich.console import Console
from rich.pretty import Pretty
import keyboard
from .data_logging import read_and_store_data, save_data_if_needed, buffer_data_to_file


def hold_temperature(controller, data_buffer, output_filename=None, target_temp=22):
    """
    Hold the temperature at the target value indefinitely until user acknowledgment.
    Display the holding temperature at 1 Hz.

    Args:
        controller: TC-720 controller instance
        data_buffer: deque or list for holding logged data
        output_filename: path to file for storing logged data
        target_temp: desired hold temperature in °C
    """
    console = Console()
    console.rule("[bold red]Holding Temperature[/bold red]")
    console.print(f"Tset = {target_temp}°C. Press 's' to continue.", style="bold green")
    console.print("You might need to press multiple times for it to register.")

    controller.set_active()
    controller.set_mode(0)
    controller.output_enable(True)
    controller.set_temp(target_temp)

    last_sample_time = time.time()

    if output_filename is None:
        output_filename = f"{time.strftime('%Y%m%d_%H%M%S')}_tc720_temperature.csv"
        console.print(f"Output filename not provided. Using default: {output_filename}")

    try:
        while True:
            if keyboard.is_pressed('s'):
                console.rule("[bold green]User Triggered Exit[/bold green]")
                console.print(f"Saving {len(data_buffer)} datapoints to {output_filename}")
                buffer_data_to_file(data_buffer, output_filename)
                break

            current_time = time.time()
            if current_time - last_sample_time >= 1.0:
                last_sample_time = current_time
                read_and_store_data(controller, data_buffer, function_args={
                    'get_temp': None,
                    'get_set_temp': None,
                    'get_output_percent': None,
                    'get_stage_pointer': None
                })
                save_data_if_needed(data_buffer, output_filename)

                if data_buffer:
                    latest_data = data_buffer[-1]
                    console.clear()
                    console.print(Pretty(latest_data), style="bold green")
                    console.print(f"Tset = {target_temp}°C. Press 's' to continue", style="bold green")

            time.sleep(0.05)

    except KeyboardInterrupt:
        buffer_data_to_file(data_buffer, output_filename)
        console.print("Data collection stopped.")
        controller.set_mode(0)
        controller.output_enable(False)

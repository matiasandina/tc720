import time
from collections import deque
from datetime import datetime
from rich import print
from rich.console import Console
import os
from tc720 import create_default_program_yaml, display_program_steps, load_program
from tc720 import setup_connection
from tc720 import TC720
from tc720 import hold_temperature
from tc720 import run_ramp_soak_program


buffer_length = 300 #gives you 5 minutes of data at 1 Hz

output_filename = f"{datetime.now().isoformat(timespec='seconds').replace(':', '').replace('-', '')}_tc720_temperature.csv"


def clear_program(controller, var_display_console):
    '''
    Clears the program in the controller.
    '''
    var_display_console.print("[yellow]Clearing existing sequence...This will take a while[/yellow]")
    controller.clear_sequence()
    time.sleep(0.5)  # allow time for internal clear
    var_display_console.print("[green]Sequence cleared![/green]")

def send_program(controller, program, var_display_console):
    '''
    Sends the program to the controller.
    '''
    for step in program['locations']:
        var_display_console.print(f"Loading step {step}")
        # For whatever reason, the controller might switch back to mode 0 or whatever (maybe data corruption?)
        # just in case, before loading the step, we should set the mode to 1
        if controller.get_mode() != 1:
            controller.set_mode(1)

        controller.set_single_sequence(location=step['location'], 
                                       temp=step['temp'],
                                       ramp_time=step['ramp_time'], 
                                       soak_time=step['soak_time'],
                                       repeats=step['repeats'], 
                                       go_to=step.get('go_to'))
        time.sleep(0.1)
        controller.set_location_proportional(location=step['location'], bandwidth = step['P'])
        controller.set_location_integral(location=step['location'], gain=step['I'])
        controller.set_location_derivative(location=step['location'], gain=step['D'])



def show_main_menu(controller, data_buffer):
    console = Console()
    console.print("[bold blue]Welcome to the TC-720 Ramp/Soak Program Controller[/bold blue]")

    while True:
        console.print("\n[bold yellow]Main Menu[/bold yellow]")
        console.print("1. Create Default Program YAML")
        console.print("2. Load and Display Program from .yaml")
        console.print("3. Hold Temperature")
        console.print("4. Hold + Run Ramp/Soak Program")
        console.print("5. Exit")

        choice = input("Enter your choice (1-5): ").strip()

        if choice == '1':
            create_default_program_yaml()
        elif choice == '2':
            program_yaml = input("Enter the path to the program YAML file: ").strip()
            program = load_program(program_yaml)
            display_program_steps(program)
        elif choice == '3':
            target_temp = float(input("Enter the target temperature (°C): ").strip())
            output_filename = input("Enter the output filename (Enter for default: temperature_data.csv): ").strip()
            output_filename = None if output_filename == "" else output_filename
            hold_temperature(controller, data_buffer, output_filename=output_filename, target_temp=target_temp)
        elif choice == '4':
            # Setup timer run method
            timer_run_method = controller.get_timer_run_method()
            if timer_run_method == 1:
                console.print("[bold red]Warning: Ramp/Soak Timer is based on sensor temperature (might be unstable).[/bold red]")
                change_method = input("Do you want to change the timer run method? (yes/no): ").strip().lower()
                if change_method in ['yes', 'y']:
                    controller.set_timer_run_method(0)
                    console.print("[bold green]Timer run method set to use set temperature.[/bold green]")
            else:
                console.print("[bold green]Timer run method is set to use set temperature.[/bold green]")
            
            time.sleep(2)
            ramp_soak_delta = controller.get_ramp_soak_delta()
            console.print(f"Current Ramp/Soak Delta: {ramp_soak_delta}")
            if ramp_soak_delta != 1.0:
                console.print(f"[bold red]Ramp/Soak delta might be too big/small: {ramp_soak_delta}.[/bold red]")
                new_delta = input("Enter a proper value for Ramp/Soak delta (recommended is 1): ").strip()
                new_delta = float(new_delta) if new_delta else 0.1
                controller.set_ramp_soak_delta(new_delta)
                console.print(f"[bold green]Ramp/Soak delta set to {new_delta}.[/bold green]")
            # Check whether "ramp_soak_temp.yaml" exists in the current directory. If not, offer to enter the path.
            # Otherwise, tell the user you are going with the existing "ramp_soak_temp.yaml"
            default_yaml = "ramp_soak_temp.yaml"
            if os.path.exists(default_yaml):
                console.print(f"[bold green]Using existing {default_yaml} in the current directory.[/bold green]")
                program_yaml = default_yaml
            else:
                program_yaml = input("{default_yaml} not found in dir. Enter the path to the program YAML file: ").strip()
            # Hold temperature before running the program
            input("Press ENTER to continue:  ")
            # TODO: there are issues with file extension and usign the same file in hold and ramp_soak
            output_filename = input("Enter the output filename (ENTER for default): ").strip()
            output_filename = f"{time.strftime('%Y%m%d_%H%M%S')}_tc720_temperature.csv" if output_filename == "" else f"{time.strftime('%Y%m%d_%H%M%S')}_{output_filename}"
            hold_temperature(controller, data_buffer, output_filename=output_filename, target_temp=22)
            run_ramp_soak_program(controller, data_buffer, program_yaml=program_yaml, output_filename=output_filename)
            break
        elif choice == '5':
            console.print("[bold red]Exiting...[/bold red]")
            break
        else:
            console.print("[bold red]Invalid choice. Please enter a number between 1 and 5.[/bold red]")


def main():
    port = setup_connection()
    if not port:
        print("[bold red]No serial port found. Please connect the controller and try again.[/bold red]")
        return
    # just in case initialize with default 22, which shouldn't be too far away from room temp
    controller = TC720(port, default_temp = 22)
    # The controller set to idle on init is a better strategy than the default settings
    # default_temp = 20, which will trigger power 100% or -100% to achieve
    # before making a breaking change to the module, 
    controller.output_enable(False)
    controller.set_timer_run_method(1)
    controller.set_ramp_soak_delta(1)    
    # Buffer for data collection
    # 5 minutes buffer if collecting every second
    data_buffer = deque(maxlen=buffer_length) 
    show_main_menu(controller, data_buffer)
    print("Exiting TC-720 Controller...")

if __name__ == "__main__":
    main()
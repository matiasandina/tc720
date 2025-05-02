import yaml
from rich import print
from rich.table import Table

def ask_user_to_confirm(message="Confirm to proceed"):
    response = input(f"{message} (y/n): ").strip().lower()
    return response in ['y', 'yes']


def save_program_copy(program, output_filename):
    yaml_filename = output_filename.replace("temperature.csv", "program.yaml")
    with open(yaml_filename, 'w') as file:
        yaml.dump(program, file, sort_keys=False)
    return yaml_filename

def display_program_steps(program):
    table = Table(title="Program Loaded into TC-720")
    table.add_column("Location", justify="right", style="cyan", no_wrap=True)
    table.add_column("Temp (°C)", justify="right", style="magenta")
    table.add_column("Ramp Time (s)", justify="right", style="green")
    table.add_column("Soak Time (s)", justify="right", style="green")
    table.add_column("P", justify="right", style="yellow")
    table.add_column("I", justify="right", style="yellow")
    table.add_column("D", justify="right", style="yellow")
    table.add_column("Repeats", justify="right", style="red")
    table.add_column("Go To", justify="right", style="red")

    for step in program['locations']:
        table.add_row(
            str(step['location']),
            str(step['temp']),
            str(step['ramp_time']),
            str(step['soak_time']),
            str(step['P']),
            str(step['I']),
            str(step['D']),
            str(step['repeats']),
            str(step['go_to'])
        )
    print(table)

def create_default_program_yaml(filename="default_temperature_program.yaml"):
    default_program = {
        "locations": [
            {"location": i, "temp": 20, "ramp_time": 0, "soak_time": 0,
            "P": 22, "I": 1, "D": 0, "repeats": 0, "go_to": 0}
            for i in range(1, 9)
        ]
    }
    with open(filename, 'w') as file:
        yaml.dump(default_program, file, sort_keys=False)
    print(f"Default program file created: {filename}")

def load_program(program_yaml):
    with open(program_yaml, 'r') as f:
        program = yaml.safe_load(f)

    for location in program.get('locations', []):
        if location.get('go_to') in [0, None]:
            location['go_to'] = None
        for key in ['location', 'ramp_time', 'soak_time', 'repeats', 'go_to']:
            if key in location and location[key] is not None:
                location[key] = int(location[key])
        for key in ['temp', 'P', 'I', 'D']:
            if key in location and location[key] is not None:
                location[key] = float(location[key])

    return program

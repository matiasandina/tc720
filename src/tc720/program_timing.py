from rich.console import Console
from rich.table import Table

def calculate_single_step_duration(location, repeat):
    ramp_time = location['ramp_time']
    soak_time = location['soak_time']
    step_time = ramp_time + soak_time
    return {
        'location': location['location'],
        'temp': location['temp'],
        'ramp_time': ramp_time,
        'soak_time': soak_time,
        'step_time': step_time,
        'repeat': repeat
    }

def calculate_program_timing(program):
    executed_steps = []
    total_time = 0
    for step in program['locations']:
        repeats = 0 if step['repeats'] is None else step['repeats']
        step_duration = calculate_single_step_duration(step, 0)
        executed_steps.append(step_duration)
        total_time += step_duration['step_time']
        if repeats == 0:
            continue
        for repeat in range(1, repeats + 1):
            if step['go_to'] is not None:
                go_to_index = step['go_to'] - 1
                go_to_step = program['locations'][go_to_index]
                go_to_duration = calculate_single_step_duration(go_to_step, repeat)
                executed_steps.append(go_to_duration)
                total_time += go_to_duration['step_time']
            step_duration = calculate_single_step_duration(step, repeat)
            executed_steps.append(step_duration)
            total_time += step_duration['step_time']
    return {
        'steps': executed_steps,
        'total_time': total_time
    }

def display_program_timing(result):
    console = Console()
    table = Table(title="Program Timing Breakdown")
    table.add_column("Step", justify="right")
    table.add_column("Location", justify="right")
    table.add_column("Target Temp (°C)", justify="right")
    table.add_column("Ramp Time (s)", justify="right")
    table.add_column("Soak Time (s)", justify="right")
    table.add_column("Step Total Time (s)", justify="right")
    table.add_column("Repeat #", justify="right")
    for i, step in enumerate(result['steps'], start=1):
        table.add_row(
            str(i),
            str(step['location']),
            f"{step['temp']:.2f}",
            str(step['ramp_time']),
            str(step['soak_time']),
            str(step['step_time']),
            str(step['repeat'])
        )
    console.print(table)
    console.print(f"[bold green]Total Program Time: {result['total_time']} seconds or {round(result['total_time']/60)} minutes [/bold green]")


def display_program_comparison(yaml_program, controller_program):
    console = Console()
    table = Table(title="[bold yellow]Expected (YAML) vs Loaded (Controller)[/bold yellow]")
    headers = ["Location", "Temp", "Ramp", "Soak", "Repeats", "Go To"]
    for h in headers:
        table.add_column(h + " (YAML)", justify="right", style="cyan")
        table.add_column(h + " (Controller)", justify="right", style="magenta")

    for step_yaml, step_hw in zip(yaml_program['locations'], controller_program):
        values_yaml = [
            step_yaml['location'], step_yaml['temp'], step_yaml['ramp_time'],
            step_yaml['soak_time'], step_yaml['repeats'], step_yaml['go_to']
        ]
        values_hw = [
            int(float(x)) if x.endswith(".0") else float(x)
            for x in step_hw[:6]  # assuming controller_program is a list of lists of strings
        ]
        for idx in [1, 2, 3]:
            values_hw[idx] = round(values_hw[idx], 1)  # for floats
        values_hw[4] = int(values_hw[4])
        values_hw[5] = int(values_hw[5]) if values_hw[5] != 0 else None

        table.add_row(*map(str, values_yaml + values_hw))
    console.print(table)
    console.print("[bold red]Please confirm that YAML and Controller match visually.[/bold red]")

def get_reset_program():
    return {
        "locations": [
            {"location": i, "temp": 20, "ramp_time": 0, "soak_time": 0,
             "P": 22, "I": 1, "D": 0, "repeats": 0, "go_to": None}
            for i in range(1, 9)
        ]
    }

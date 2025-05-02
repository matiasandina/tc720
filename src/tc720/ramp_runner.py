import time
from rich.console import Console
from rich.pretty import Pretty
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.text import Text
from .program_utils import ask_user_to_confirm, load_program, save_program_copy
from .program_timing import calculate_program_timing, display_program_timing
from .data_logging import parse_ramp_soak_status, read_and_store_data, save_data_if_needed, buffer_data_to_file

import logging

logger = logging.getLogger("tc720")

def send_program(controller, program, var_display_console):
    for step in program['locations']:
        var_display_console.print(f"Loading step {step}")
        if controller.get_mode() != 1:
            controller.set_mode(1)

        controller.set_single_sequence(location=step['location'], 
                                       temp=step['temp'],
                                       ramp_time=step['ramp_time'], 
                                       soak_time=step['soak_time'],
                                       repeats=step['repeats'], 
                                       go_to=step.get('go_to'))
        time.sleep(0.05)
        controller.set_location_proportional(location=step['location'], bandwidth=step['P'])
        controller.set_location_integral(location=step['location'], gain=step['I'])
        controller.set_location_derivative(location=step['location'], gain=step['D'])


def colorize_power(power):
    text = Text(f"{power:+.2f}%")
    if power > 0:
        text.stylize("red")
    elif power < 0:
        text.stylize("blue")
    else:
        text.stylize("dim")
    return text

def monitor_ramp_soak(controller, data_buffer, output_filename, program_steps=None):
      console = Console()
      current_location = 1
      current_phase = None
      phase_start_time = time.time()
      program_start_time = time.time()
      step_history = []
      last_step = None
  
      with Live(refresh_per_second=4) as live:
          try:
              while True:
                  new_phase = parse_ramp_soak_status(controller.get_ramp_soak_status())
                  if new_phase != current_phase:
                      phase_start_time = time.time()
                      current_phase = new_phase
  
                  elapsed_phase_time = time.time() - phase_start_time
                  total_elapsed_time = time.time() - program_start_time
                  next_location = controller.get_repeat_location(current_location)
  
                  read_and_store_data(controller, data_buffer, function_args={
                      'get_temp': None,
                      'get_set_temp': None,
                      'get_output_percent': None,
                      'get_stage_pointer': None
                  })
                  save_data_if_needed(data_buffer, output_filename)
  
                  if data_buffer:
                      latest = data_buffer[-1]
                      stage_pointer = latest.get("stage_pointer", 0)
                      step = stage_pointer + 1
  
                      if step != last_step:
                          step_history.append(str(step))
                          if len(step_history) > 20:
                              step_history.pop(0)
                          last_step = step
  
                      table = Table(title="TC720 Ramp Soak Monitor")
                      table.add_column("Metric", style="bold cyan")
                      table.add_column("Value", style="bold white")
  
                      table.add_row("Current Phase", current_phase)
                      table.add_row("Step (Index +1)", str(step))
                      table.add_row("Stage Pointer", str(stage_pointer))
                      table.add_row("Local Time", latest.get("timestamp_local", "--"))
                      table.add_row("Sensor Temp (°C)", f"{latest['sensor1_temp']:.2f}")
                      table.add_row("Set Temp (°C)", f"{latest['set_temp']:.2f}")
                      table.add_row("Power Output", colorize_power(latest['power_output_percent']))
                      table.add_row("Elapsed Phase Time", f"{elapsed_phase_time:.1f} s")
                      table.add_row("Total Program Time", f"{total_elapsed_time:.1f} s")
  
                      step_seq = " → ".join(step_history)
                      table.add_row("Step History", step_seq)
  
                      if program_steps:
                          step_info = Pretty(program_steps)
                          panel = Panel(step_info, title="Program Steps", border_style="cyan")
                          live.update(Panel.fit(table, title="[bold]TC720 Ramp Sequence[/bold]"), refresh=True)
                          console.print(panel)
                      else:
                          live.update(table, refresh=True)
  
                      if latest['status'] == "No sequence running" and latest['stage_pointer'] == 0:
                          console.clear()
                          console.rule("Sequence Finished!")
                          console.print(f"Saving data to {output_filename}")
                          buffer_data_to_file(data_buffer, output_filename)
                          controller.idle_soak()
                          break
  
                  if new_phase == "Ramp stage" and next_location != current_location:
                      current_location = next_location
  
                  time.sleep(1)
  
          except KeyboardInterrupt:
              buffer_data_to_file(data_buffer, output_filename)
              console.print("Data collection stopped.")
              controller.idle_soak()

def run_ramp_soak_program(controller, data_buffer, program_yaml, output_filename):
    console = Console()
    console.rule("[bold red]Ramp Soak Program[/bold red]")

    program = load_program(program_yaml)
    program_timing = calculate_program_timing(program)
    display_program_timing(program_timing)
    console.print("[bold red]Acknowledge Program Timing[/bold red]")
    user_acknowledged = ask_user_to_confirm()
    
    if not user_acknowledged:
        console.print("[bold red]Program aborted by user.[/bold red]")
        raise SystemExit("Program timing not acknowledged.")
    
    console.print("[bold green]Program acknowledged. Proceeding to load into TC-720...[/bold green]")
    console.print("Loading program might take a while...")
    
    controller.set_active()
    controller.set_mode(1)
    controller.output_enable(True)

    while controller.get_mode() != 1:
        console.print("Waiting for controller to switch to mode 1...")
        time.sleep(0.5)

    send_program(controller, program, console)

    console.print("Verify Program Loaded into TC-720:")
    time.sleep(0.5)
    hw_program = controller.get_loaded_program(location="all")
    print(hw_program)

    if ask_user_to_confirm("Confirm that the loaded program matches the YAML file?"):
        yaml_fn = save_program_copy(program, output_filename)
        console.print(f"Saved Program copy at {yaml_fn}")
        controller.start_soak()
        monitor_ramp_soak(controller, data_buffer, output_filename)
    else:
        console.print("Program execution cancelled. Setting controller to idle.")
        controller.output_enable(False)

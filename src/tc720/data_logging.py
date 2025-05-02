from datetime import datetime, timezone
import pandas as pd
import os
def get_function_mapping():
    """
    Returns a dictionary mapping function names to human-readable keys.
    This is used to convert function names to more understandable keys in the data entry.
    """
    return {
        'get_temp': 'sensor1_temp',
        'get_temp2': 'sensor2_temp',
        'get_mode': 'mode',
        'get_control_type': 'control_type',
        'get_set_temp': 'set_temp',
        'get_output': 'power_output',
        'get_output_percent': 'power_output_percent',
        'get_set_output': 'set_power_output',
        'get_ramp_soak_status': 'ramp_soak_status',
        'get_soak_temp': 'soak_temp',
        'get_ramp_time': 'ramp_time',
        'get_soak_time': 'soak_time',
        'get_repeats': 'repeats',
        'get_repeat_location': 'repeat_location',
        'get_stage_pointer': 'stage_pointer',
        'get_stage_repeat_location': 'stage_repeat_location'
    }



def ping_read_functions(controller, function_args):
    '''
    Executes functions on a given controller object, passing single arguments or no arguments.

    Args:
        controller (object): The controller object containing the functions to be called.
        function_args (dict): A dictionary where keys are function names, and values are arguments
                              (or None for no arguments).

    Returns:
        dict: A dictionary where the keys are the function names and the values are the results of 
              the function calls, or an error message if the function is not callable or not found.
    '''

    results = {}
    for func_name, arg in function_args.items():
        try:
            func = getattr(controller, func_name)
            if callable(func):
                # Call with argument if provided, otherwise call with no arguments
                results[func_name] = func(arg) if arg is not None else func()
            else:
                results[func_name] = "Not callable"
        except AttributeError:
            results[func_name] = "Function not found"
        except TypeError as e:
            results[func_name] = f"TypeError: {e}"
    return results

def parse_ramp_soak_status(status):
    """
    Parse the ramp/soak status to a single value.
    The controller returns something like 000, 101, or 110.
    The module will give you a list of all the active states or "No sequence running" for '000'.
    This function identifies the most salient element based on priority.

    Args:
        status (list or str): The status string or list from the controller.

    Returns:
        str: The parsed status.
    """
    if status == "No sequence running":
        return "No sequence running"
    
    # Priority order: Ramp stage > Soak stage > Sequence Running
    match status:
        case _ if "Ramp stage" in status:
            return "Ramp stage"
        case _ if "Soak stage" in status:
            return "Soak stage"
        case _ if "Sequence Running" in status:
            return "Sequence Running" # should never return this
        case _:
            return "Unknown status"

def read_and_store_data(controller, data_buffer, function_args):
    """
    Reads data from a controller, processes it, and stores it in a data buffer.

    Args:
        controller (object): The controller object to read data from.
        data_buffer (list): The buffer where the processed data entries will be stored.
        function_args (dict): A dictionary where keys are function names and values are arguments (or None for no arguments).
    Returns:
        None
    """

    # Get current timestamps
    current_dt = datetime.now()
    timestamp_local = current_dt.isoformat()
    timestamp_utc = current_dt.astimezone(timezone.utc).isoformat()

    # Ping the functions with their arguments
    results = ping_read_functions(controller, function_args)

    # Parse the status to a single value
    raw_status = controller.get_ramp_soak_status()
    parsed_status = parse_ramp_soak_status(raw_status)
    #print(f"Raw Status Returned is: {raw_status}, Parsed Status is: {parsed_status}")

    # Create a data entry with timestamps
    data_entry = {
        'timestamp_utc': timestamp_utc,
        'timestamp_local': timestamp_local,
        'status': parsed_status
    }

    # Add the results to the data entry using the mapping dictionary
    function_mapping = get_function_mapping()
    for func_name, result in results.items():
        human_readable_key = function_mapping.get(func_name, func_name)
        data_entry[human_readable_key] = result

    # Append the data entry to the buffer
    data_buffer.append(data_entry)

def save_data_if_needed(data_buffer, filename="temperature_data.csv"):
    if len(data_buffer) == data_buffer.maxlen:
        buffer_data_to_file(data_buffer, filename)
        data_buffer.clear()

def buffer_data_to_file(buffer, filename):
    """
    Save buffer data to a CSV file. Appends data without rewriting headers if the file exists.
    Args:
        buffer (deque or list): Buffer containing dictionaries of data.
        filename (str): Path to the file where the data will be saved.
    """
    # Convert deque or list to a DataFrame
    data_list = list(buffer)
    df = pd.DataFrame(data_list)

    # Check if the file exists
    file_exists = os.path.isfile(filename)

    # Save DataFrame to CSV file
    df.to_csv(path_or_buf=filename, index=False, mode='a', header=not file_exists)
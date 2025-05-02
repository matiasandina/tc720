# TC-720 Temperature Controller

[![Read the Docs](https://readthedocs.org/projects/tc720/badge/?version=latest)](https://tc720.readthedocs.io/en/latest/)


This project provides a Python package to control the TC-720 temperature controller from TE Technology Inc. The TC-720 is a versatile temperature controller capable of maintaining a fixed temperature, executing ramp/soak programs, and operating in proportional+dead band mode.

## Features

- **Normal Set Mode**: Maintain a fixed temperature, output power, or analog output.
- **Ramp/Soak Mode**: Program and execute temperature sequences with up to 8 steps.
- **Proportional+Dead Band Mode**: Limited support for this mode.
- **Real-Time Monitoring**: Retrieve current temperature, output power, and program status.
- **PID Control**: Configure proportional, integral, and derivative gains for precise temperature control.
- **Data Logging**: Collect and save temperature and controller data during operation.

## Installation

### From repo

1. Clone the repository:
```bash
   git clone <repository-url>
   cd tc720
```

2. Install dependencies:
``` bash
pip install -r requirements.txt
```

3. Install the package:

```bash
pip install .
```

## Usage

Finding the Controller Address
Use the find_address function to locate the TC-720 controller:
```python
from Py_TC720 import find_address

port = find_address()
print(f"Controller found at: {port.device}")
```

Initializing the Controller
Create a TC720 instance to communicate with the controller:
```python
from Py_TC720 import TC720

controller = TC720(address="COM3", default_temp=22, verbose=True)
```

Setting a Fixed Temperature
Set the controller to maintain a specific temperature:
```python
controller.set_mode(0)  # Normal Set Mode
controller.set_temp(25.0)  # Set temperature to 25°C
```

Programming a Ramp/Soak Sequence
Define and load a ramp/soak program:
```python
controller.set_mode(1)  # Ramp/Soak Mode
controller.set_single_sequence(location=1, temp=22, ramp_time=60, soak_time=300, repeats=2, go_to=2)
controller.set_single_sequence(location=2, temp=16, ramp_time=60, soak_time=300, repeats=0, go_to=1)
controller.start_soak()
```

Monitoring and Logging Data
Retrieve real-time data from the controller:

Stopping the Controller
Stop the ramp/soak program and set the controller to idle:
```python
controller.idle_soak()
controller.set_idle()
```

## File Structure
`Py_TC720.py`: Core library for communicating with the TC-720 controller.
`ramps.py`: High-level utilities for managing ramp/soak programs and data logging.
`ramp_soak_temp.yaml`: Example YAML file defining a ramp/soak program.
`pyproject.toml`: Project metadata and build configuration.
`requirements.txt`: List of required Python packages.

## License

This project is licensed under the MIT License. See LICENSE.txt for details.

## Acknowledgments
Original implementation by Lars E. Borm.
Updated and extended by Matias Andina.
Based on the TC-720 operating manual from TE Technology Inc.

## Issues

Please file issues to improve the package
import serial
import platform
from serial.tools import list_ports
import warnings

#_______________________________________________________________________________
#   FIND SERIAL PORT
def find_address(identifier = None):
    """
    Find the address of a serial device. It can either find the address using
    an identifier given by the user or by manually unplugging and plugging in 
    the device.
    Input:
    `identifier`(str): Any attribute of the connection. Usually USB to Serial
        converters use an FTDI chip. These chips store a number of attributes
        like: name, serial number or manufacturer. This can be used to 
        identify a serial connection as long as it is unique. See the pyserial
        list_ports.grep() function for more details.
    Returns:
    The function prints the address and serial number of the FTDI chip.
    `port`(obj): Returns a pyserial port object. port.device stores the 
        address.
    
    """
    found = False
    if identifier is not None:
        port = [i for i in list_ports.grep(identifier)]
        
        if len(port) == 1:
            print('Device address: {}'.format(port[0].device))
            found = True
        elif len(port) == 0:
            print('''No devices found using identifier: {}
            \nContinue with manually finding USB address...\n'''.format(identifier))
        else:
            for p in port:
                print('{:15}| {:15} |{:15} |{:15} |{:15}'.format('Device', 'Name', 'Serial number', 'Manufacturer', 'Description') )
                print('{:15}| {:15} |{:15} |{:15} |{:15}\n'.format(str(p.device), str(p.name), str(p.serial_number), str(p.manufacturer), str(p.description)))
            warnings.warn(f"Selected port identifier {identifier} returned multiple devices, see above. Returning list of devices")
            return port

    if not found:
        print('Performing manual USB address search.')
        while True:
            input('    Unplug the USB. Press Enter if unplugged...')
            before = list_ports.comports()
            input('    Plug in the USB. Press Enter if USB has been plugged in...')
            after = list_ports.comports()
            port = [i for i in after if i not in before]
            if port != []:
                break
            print('    No port found. Try again.\n')
        print('Device address: {}'.format(port[0].device))
        try:
            print('Device serial_number: {}'.format(port[0].serial_number))
        except Exception:
            print('Could not find serial number of device.')
    
    return port[0]

#==========================================================================
#    Functions for sending and reading messages
#==========================================================================

def int_to_hex(integer):
    """
    Formats integers to a 4-character hexadecimal string for message construction.
    Supports negative values using two's complement. Max magnitude: 32768.

    Args:
        integer (int): Value to convert

    Returns:
        str: 4-character hex string
    """
    if abs(integer) > 32768:
        raise ValueError('Cannot encode integers larger than ±32768 in 4-digit hex.')

    if integer < 0:
        integer = int((0.5 * 2**16) - integer)

    return '{h:0>4}'.format(h=hex(integer)[2:])


def response_to_int(response):
    """
    Convert a 4-character hex response from the device into an integer.
    Handles negative values using two's complement.

    Args:
        response (bytes or str): Response from device, e.g., b'*XXXX60^'

    Returns:
        int: Interpreted integer value
    """
    if isinstance(response, bytes):
        response = response.decode()

    value = int(response[1:5], base=16)
    if value > 0.5 * (2**16):
        value = -(2**16 - value)

    return value

def make_checksum(message):
    """
    Compute the 2-character ASCII hex checksum for a message. It calculates the 8 bit, modulo 256 checksum in the format of 2 ASCII hex characters.

    Args:
        message (str | list | bytes): Message to compute checksum on

    Returns:
        str: 2-character checksum string
    """
    if isinstance(message, list):
        message = ''.join(message)
    if isinstance(message, bytes):
        message = message.decode()

    checksum = hex(sum(message[1:7].encode('ascii')) % 256)[-2:]
    return checksum.zfill(2)

def check_checksum(response):
    """
    Validate the checksum of a response message from the TC-720.

    Args:
        response (bytes | str): Full 8-character response from the controller (e.g., '*0898d9^')

    Returns:
        bool: True if checksum is valid, False otherwise
    """
    if isinstance(response, bytes):
        response = response.decode()

    # Extract the 4-character payload used in checksum calculation (characters 1-4)
    payload = response[1:5]

    # Extract the checksum string sent by the controller (characters 5-6)
    expected_checksum = response[5:7].lower()

    # Calculate checksum as the sum of ASCII values of the payload, mod 256
    checksum_value = sum(payload.encode('ascii')) % 256

    # Format as two-digit lowercase hex string (e.g., 'd9' not '0xd9' or '9')
    calculated_checksum = f"{checksum_value:02x}"

    # Debug log for inspection (optional, remove or gate with a flag)
    #print(f"[Checksum Debug] Payload: '{payload}', Expected: '{expected_checksum}', Calculated: '{calculated_checksum}'")

    # Return comparison result
    return expected_checksum == calculated_checksum

def message_builder(command, value='0000'):
    """
    Constructs a properly formatted TC-720 message.

    Format: (stx)CCDDDDSS(etx) where
        * = Start
        CC = 2-char hex command
        DDDD = 4-char hex data
        SS = 2-char checksum
        \r = End

    Args:
        command (str): 2-character hex string command
        value (str): 4-character hex string data (default '0000')

    Returns:
        list[str]: List of 10 ASCII characters representing the message
    """
    if not isinstance(command, str) or len(command) != 2:
        raise ValueError(f"Invalid command: '{command}'. Must be a 2-character string.")

    if not isinstance(value, str) or len(value) != 4:
        raise ValueError(f"Invalid value: '{value}'. Must be a 4-character string.")

    message = ['*', command[0], command[1],
               value[0], value[1], value[2], value[3],
               '0', '0', '\r']

    checksum = make_checksum(message)
    message[7:9] = checksum[0], checksum[1]

    return message

def setup_connection(serial_number=None):
    #TODO: serial_number to be implemented isntead of hard coded    
    # Check the operating system
    if platform.system() == "Windows":
        # Use "COM" to find the address on Windows
        # Try to use the serial number to find the port
        ports = find_address(identifier="COM")
        if isinstance(ports, list):
            for port in ports:
                # TODO: super hard coding the serial number here
                # FTDI is not the actual manufacturer
                if port.manufacturer == 'FTDI' and port.serial_number == 'A505HG59A':
                    return port.name
        elif isinstance(ports, serial.tools.list_ports_common.ListPortInfo):
            if ports.manufacturer == 'FTDI' and ports.serial_number == 'A505HG59A':
                return ports.name
        return None
    else:
        # TODO: Not worked out at all... this should be for linux
        port = find_address('dev/ttyUSB')


################################################################################
#Python 3 package to control the TC-720 temperature controller from:
#TE Technology Inc. (https://tetech.com/)

#Date: 7 September 2018, November 2024
#Author: Lars E. Borm , Matias Andina
#E-mail: lars.borm@ki.se or larsborm@hotmail.com, mandina@mit.edu
#Python version: 3.5.4, 3.12

#Based on TC-720 operating Manual; Appendix B - USB Communication
#https://tetech.com/product/tc-720/

#NOTE!
#Not all possible functions of the TC-720 are implemented in this code.
#Hopefully this code in combination with the manual provides enough support to
#implement the other functions. If you do please update the project to improve.

################################################################################

#Basic Operation:

#First, find the address of the temperature controller by using the:
#"find_address()" function. 

#Then initialize the connection with the controller:
#import tc720
#address = tc720.serial_utils.find_address()
#my_device = tc720.TC720(address, name='hotstuff', verbose=True)

#The temperature controller had different modes of operation which are set
#by changing the mode using the set_mode() function:
# 0: Normal Set Mode; This mode is used to hold one temperature (0), one output 
#   power(1) or an analogue output by another power source (2). Set one of
#   these 3 control types using the set_control_type() function.
# 1: Ramp/Soak Mode: This mode is used to program a specific temperature and
#   and time sequence.
# 2: Proportional+Dead Band mode; (limited to no support yet)

# The machine will default to the Normal set mode that hold one specific
# temperature. Default is 20C. The temperature can be set using: set_temp(X)

#If you want a more custom temperature cycle:
#Set the machine in Ramp/Soak mode using: set_mode(1)
#To program the temperature schedule:
#The controller has 8 'locations' that can hold information for a temperature
#cycle. For each location you need to specify the desired temperature, the 
#time it should hold that temperature (soak time), the time it should take to
#reach the desired temperature (ramp time), the number of times this location
#should be performed (repeats) and the next step/location that should be
#performed if the current location is fully executed (repeat location).
#These 8 steps are the same as the 8 slots in the graphical interface that is
#provided by TE Technologies INC.
#You can start the execution of the 8 location by calling "start_control()",
#and stop it by calling "set_idle()".
################################################################################

# imports

from .serial_utils import int_to_hex, response_to_int
from .serial_utils import check_checksum
from .serial_utils import message_builder
import serial
import time
import numpy as np
from collections import deque
import warnings
import inspect



#==============================================================================
#   TC-720 class
#==============================================================================

class TC720():
    """
    Class to control the TC-720 temperature controller from TE Technology Inc. 
    
    """
    def __init__(self, address, name = 'TC-720', mode = 0, control_type = 0,
                 default_temp = 20, verbose = False):
        """
        Input:
        `address`(str): The address of TC-720. Use the "find_address()" function
            to find the address. It should have the format of 'ComX' on Windows
            and 'dev/ttyUSBX' in linux, where X is the address number.
        `name`(str): Custom name of the TC-720. Useful if there are multiple
            units connected. Default = TC-720.
        `mode`(int 0-2): The mode of operation:
            0: Normal Set Mode; maintain one value. This can be one temperature
            one output power or output by an external power source. See 
            control_type for options.
            1: Ramp/Soak Mode: This mode is used to program a specific 
            temperature and time sequence.
            2: Proportional+Dead Band mode; (limited to no support yet)
            Default = 0 (set one value)
        `control_type`(int 0-2): If mode is 0 the controller can maintain
            one temperature (0), one output power(1) or an analogue 
            output by another power source (2).
            Default = 0 (set one temperature
        `default_temp`(int): Default temperature in degree centigrade.
            Default = 20C
        `verbose`(bool): Option to print status messages.

        """
        self.address = address
        self.name = name
        self.mode = mode
        self.control_type = control_type
        self.default_temp = default_temp
        self.verbose = verbose
        self.verboseprint = print if self.verbose else lambda *a, **k: None
        self.CHECKSUM_ERROR_RESPONSE = b'*XXXX60^'  # Controller error response per TC-720 manual

        #make connection with controller
        self.ser = serial.Serial(self.address, timeout= 2, baudrate=230400, stopbits=serial.STOPBITS_ONE, parity=serial.PARITY_NONE)
        self.verboseprint('Made connection with temperature controller: {}'.format(self.name))

        #Set the machine into temperature control
        self.set_temp(self.default_temp)
        self.set_mode(self.mode)
        self.set_control_type(self.control_type)
        self.verboseprint('Mode set to: {}, control type set to: {}, temperature set to: {}C'.format(self.mode, self.control_type, self.default_temp))

    def send_message(self, message, write=False):
        """
        Send message to the temperature control unit. Use the 
        message_builder()function to construct the message in the right 
        format. This function will call lower level functions that handle common read/write and 
        'special' read/write that requires indexing (e.g., when using ramp-soak). 
        Input:
        `message`(list): Message with 10 bits as individual ASCII stings.
            Structure of message: (stx)CCDDDDSS(etx)
                (stx): Start text character = '*'
                CC: Command, 2 bits
                DDDD: Value, 4 bits
                SS: Checksum, 2 bits
                (etx): End of text character = '\r'
            Format: ['*', 'C', 'C', 'D', 'D', 'D', 'D', 'S', 'S', '\r']
        `write`(bool): Small trick to make sure a certain message is dealt with
            as a write command (opposed to a read command). The problem is that 
            if a zero is written to the controller the program thinks it is a
            read command because read commands sent the value '0000'.
        
        """

        # Commands needing special handling location based indexing/read/write 
        special_commands = {
            '84': 'proportional_read',    # Read proportional bandwidth
            '85': 'integral_set_index',    # Set index for integral gain
            '86': 'integral_write',        # Write integral gain
            '87': 'integral_read',         # Read integral gain
            '88': 'derivative_set_index',  # Set index for derivative gain
            '89': 'derivative_write',      # Write derivative gain
            '8a': 'derivative_read',        # Read derivative gain
            'f1': 'timer_run_method_read',  # Add f1 to handle timer run method reading
            '0a': 'stage_pointer_read',     # Add 0a to handle stage pointer reading
            'f3': 'ramp_soak_delta_read',  # Read ramp soak delta
            'f2': 'ramp_soak_delta_write',  # Write ramp soak delta
            '64': 'output_enable_read',  # Check if output is enabled
            '30': 'output_enable_write'  # Enable or disable output
        }

        # Clear reply buffer
        self.ser.read_all()
        full_message = ''.join(message).replace('\r', '')  #remove \r at the end to avoid printing issues
        command = ''.join(message[1:3])  # Command part for matching
        self.verboseprint(f"Sending message: {full_message} for command {command}")

        # Define message handling behavior based on command
        if command in special_commands.keys():
            return self._send_special_command(message)
        else:
            return self._send_standard_command(message, write)

    def _send_special_command(self, message):
        """
        Sends message once and reads single response for special commands.
        """
        for i in message:
            self.ser.write(str.encode(i))
            time.sleep(0.005)
        
        response = self.read_message(detect_error=False)
        self.verboseprint(f"Response for special command: {response}")
        return response

    def _send_standard_command(self, message, write):
        """
        Standard handling with up to 5 retries for acknowledgment in write mode.
        """
        if ''.join(message[3:7]) == '0000' and not write:  # Read command
            for i in message:
                self.ser.write(str.encode(i))
                time.sleep(0.005)
        else:
            self._send_standard_write_command(message)

    def _send_standard_write_command(self, message):
        for n in range(5):
            for i in message:
                self.ser.write(str.encode(i))
                time.sleep(0.005)

            response = self.read_message(detect_error=False)
            if self._handle_standard_response(response, message):
                break
            time.sleep(0.05)
        else:
            raise Exception('Could not correctly send "{}" to temperature controller: {}. {}'.format(''.join(message[:-1]), self.name, self.checksum_error))

    def _handle_standard_response(self, response, message):
        if response[1:5].decode() == ''.join(message[3:7]):
            return True
        if response == self.CHECKSUM_ERROR_RESPONSE:
            self.checksum_error = 'Checksum error'
            print('    {} Error: Checksum error.'.format(self.name))
        else:
            self.checksum_error = ''
            self.verboseprint('    {} Error: Temperature controller did not correctly receive the command.'.format(self.name))
        return False        
    
    def read_message(self, timeout=1, detect_error=True):
        """
        Read a message sent by the temperature control unit. 
        
        Input
        `timeout`(int): Time in seconds in which the program will check if 
            there are messages send by the controller. If it times out it will 
            throw a warning and return an empty byte-string (b''), which will 
            probably cause an error in the rest of the code. Default = 1 second.
        `detect_error`(bool): If True, it will check if the controller reports 
            an error in the checksum of the send messages. And it will check if
            the response by the controller has an error in the checksum. It 
            will raise an error if a checksum mistake as been made. 
            Default = True.
        Returns: 
        The response by the controller as byte-string.     
        
        """
        try:
            start_time = time.time()
            while True:
                #Check if there is a response waiting to be read.
                if self.ser.in_waiting >= 8:
                    response =  self.ser.read_all()
                    
                    if detect_error:
                        #Check if there is an error in the checksum of the send message.
                        if response == self.CHECKSUM_ERROR_RESPONSE:
                            raise Exception ('{} Error: Checksum error in the send message.'.format(self.name))
                        #Check if there is an error in the checksum of the received message.
                        if not check_checksum(response):
                            raise Exception ('{} Error: Checksum error in the received message.'.format(self.name))
                        
                    return response
                
                #Timeout check
                elif (time.time() - start_time) > timeout:
                    warnings.warn(f'Timeout: no response from {self.name} within {timeout} seconds')
                    return b''
                
                else:
                    time.sleep(0.05)
        
        except Exception as e:
            print('{} Error: {}'.format(self.name, e))
            raise Exception ('Connection error with temperature control unit: {}. Error: {}'.format(self.name, e))

    #==========================================================================
    #    Read functions
    #==========================================================================

    def get_temp(self):
        """
        Read the current temperature on sensor 1.
        Returns temperature in degree Celsius with 2 decimals.
        
        """
        self.send_message(message_builder('01'))
        return response_to_int(self.read_message()) / 100

    def get_temp2(self):
        """
        Read the current temperature on sensor 2.
        Returns temperature in degree Celsius with 2 decimals.
        
        """
        self.send_message(message_builder('04'))
        return response_to_int(self.read_message()) / 100

    def get_mode(self):
        """
        Get the mode of the temperature control unit. 
        Returns mode:
            0 = Normal set
            1 = Ramp/Soak set mode
            2 = Proportional+Dead Band
        
        """
        #Ask for mode
        self.send_message(message_builder('71'))
        return response_to_int(self.read_message())

    def get_control_type(self):
        """
        Get the control mode of the temperature control unit.
        Relevant only if the mode is set to 0 (Normal set)
        Return control type:
            0 = PID, set a single fixed temperature.
            1 = Manual, set a fixed output power level.
            2 = Analog Out, Use with external variable voltage
            supply.

        """
        self.send_message(message_builder('73'))
        return response_to_int(self.read_message())

    def get_set_temp(self):
        """
        Get the current set temperature for the Normal set mode.
        Returns set temperature in degree Celsius

        """
        self.send_message(message_builder('06'))
        # TODO: I think the name of the function and command is confusing
        # this is to use in the fixed mode it doesn't work on ramps
        # FIXED DESIRED CONTROL SETTING
        # Write Command: 1c
        # Read Command: 50
        # Interpret: To send a set temperature, multiply the decimal value by 10010 and convert to hexadecimal. To read
        # the set temperature, convert the returned hexadecimal value to decimal, and then divide by 10010. 
        #self.send_message(message_builder('50'))
        return response_to_int(self.read_message()) / 100

    def get_output(self):
        """
        Get the current output level.
        Returns the current output in the range -511 to 511
        for -100% and 100% output power.

        """
        self.send_message(message_builder('02'))
        return response_to_int(self.read_message())

    def get_output_percent(self):
        """
        Get the current output level as a percentage.
        Converts the output range -511 to 511 to a percentage:
        -511 represents -100% (cooling), and 511 represents 100% (heating).
    
        Returns:
            float: Current output as a percentage (-100.0 to 100.0).
        """
        raw_output = self.get_output()  # Use the existing get_output method
        return round((raw_output / 511) * 100, 2)

    def get_set_output(self):
        """
        Get the set manual output.
        Returns the set output in the range -511 to 511
        for -100% and 100% output power.

        """
        self.send_message(message_builder('74'))
        return response_to_int(self.read_message())

    def get_ramp_soak_status(self):
        """
        Returns if the temperature control unit is running a temperature
        sequence. If it is running a sequence it returns the Ramp/Soak status.
        Returns:
        "No sequence running" or a list of currently running operations.   
        
        """
        #Ask for status
        self.send_message(message_builder('09'))
        response = self.read_message()
        #Convert to binary code where each bit marks an running operation.
        response_bit = bin(int(response[1:5], base=16))  
        status_response = '{0:03}'.format(int(response_bit[2:]))
        if status_response == '000':
            return 'No sequence running'
        else:
            # from the manual Ramp stage will 
            # convert to 101 where Bit 0 (the rightmost bit) is set and Bit 2 is set
            # So we get 101 -> ["Ramp stage", "Sequence Running"]
            status_list = ['Ramp stage', 'Soak stage', 'Sequence Running']
            return [status_list[n] for n,i in enumerate(status_response) if i == '1']
            
    def get_soak_temp(self, location):
        """
        Get the soak temperature (holding temperature) of the specified
        location.
        Input:
        `location`(int): locations 1-8
        Returns the set temperature in degree Centigrade
        
        """
        #Check input
        self.validate_data(location)
        
        #Get soak temperature
        location_code = 'a' + hex(location + 7)[-1]
        self.send_message(message_builder(location_code))
        return response_to_int(self.read_message()) / 100

    def get_ramp_time(self, location):
        """
        Get the ramp time of the specified location.
        Input:
        `location`(int): locations 1-8.
        Returns the ramp time in seconds. 
        
        """
        #Check input
        self.validate_data(location)
        
        #Get ramp time
        location_code = 'b' + hex(location + 7)[-1]
        self.send_message(message_builder(location_code))
        return response_to_int(self.read_message())

    def get_soak_time(self, location):
        """
        Get the soak time (holding time) of the specified location.
        Input:
        `location`(int): locations 1-8
        Returns the soak time in seconds.
        
        """
        #Check input
        self.validate_data(location)
        
        #Get soak time
        location_code = 'c' + hex(location + 7)[-1]
        self.send_message(message_builder(location_code))
        return response_to_int(self.read_message())

    def get_stage_pointer(self):
        """
        Retrieve the current stage pointer in the ramp/soak sequence.
        Returns:
            int: Current stage pointer value (0 through 7).
        """
        # Send the read command '0a' with no additional data
        response = self.send_message(message_builder('0a'))
        pointer = response_to_int(response)
        return pointer


    def get_repeats(self, location):
        """
        Get the number of repeats that is assigned to the specified location.
        Input:
        `location`(int): locations 1-8
        Returns the number of repeats assigned to the location.
        
        """
        #Check input
        self.validate_data(location)
        
        #Get number of repeats
        location_code = 'd' + hex(location + 7)[-1]
        self.send_message(message_builder(location_code))
        return response_to_int(self.read_message())

    def get_repeat_location(self, location):
        """
        Get the next location to execute. There are 8 locations where
        temperature settings can be stored. When one is done it will execute 
        the next one. This function fetches the next location that will be 
        performed after the one in the specified location is done.
        Input:
        `location`(int): locations 1-8
        Returns the next location in the sequence. 
        
        """
        #Check input
        self.validate_data(location)
        
        #Get number of repeats
        location_code = 'e' + hex(location + 7)[-1]
        self.send_message(message_builder(location_code))
        return response_to_int(self.read_message())

    def get_increment_counter(self):
        """
        Get the Ramp/Soak increment counter in seconds.
        Multiplies the counter value by 0.05 to convert to seconds.
        """
        self.send_message(message_builder('f5'))
        counter_value = response_to_int(self.read_message())
        return counter_value * 0.05
    
    def validate_data(self, input):
        """
            Check if the input for a location is valid.
        """
        if not isinstance(input, int) or not 1 <= input <= 8:
            raise ValueError('Invalid location: "{}", type: "{}. Must be an integer in the range 1-8.'.format(input, type(input)))


    def check_mode(self, desired_mode):
        """
        Check if the machine is in the desired mode.
        Used to check if machine is in the corresponding mode to execute a 
        function.
        Input:
        `desired_mode`(int): Desired mode 0, 1 or 2.
        Returns True or False and gives a warning if False

        """
        if desired_mode not in [0, 1, 2]:
            raise ValueError(f'Invalid input: {repr(desired_mode)}, should be integer 0, 1 or 2')

        cur_mode = self.get_mode()
        if cur_mode != desired_mode:
            # Get the name of the calling function
            calling_function = inspect.stack()[1].function
            warnings.warn(f'TC720: {self.name} is not set in the right mode to use the function "{calling_function}". Current mode: {cur_mode}, set the machine in the {desired_mode} mode using set_mode({desired_mode})')
            return False
        else:
            return True
    #==========================================================================
    #    Set functions for the operation modes
    #==========================================================================

    def set_mode(self, mode):
        """
        Set the mode of the temperature control unit.
        Input:
        `mode`(int): Mode to set. 
            0 = Normal set. Set a single temperature, a single output power 
                level or Analog out with an external power source.
                Set one of these 3 with the set_control() function
            1 = Ramp/Soak. Use the 8 ramp/soak sequences to program a 
                temperature cycle.
            2 = Proportional+Dead Band
        
        """
        #Check input
        if mode not in [0, 1, 2]:
            raise ValueError('Invalid input: {}, should be integer 0, 1 or 2'.format(repr(mode)))
        
        #Set the mode
        self.send_message(message_builder('3d',  int_to_hex(mode)), write=True)
        self.verboseprint('Mode set to: {}'.format(mode))


    def set_control_type(self, control_type):
        """
        Set the control mode of the temperature control unit.
        Relevant only if the mode is set to 0 (Normal set)
        Input:
        `control_type`:
            0 = PID, set a single fixed temperature.
            1 = Manual, set a fixed output power level.
            2 = Analog Out, Use with external variable voltage
            supply.

        """
        #Check input
        if control_type not in [0, 1, 2]:
            raise ValueError('Invalid input: {}, should be integer 0, 1 or 2'.format(repr(control_type)))

        #Check mode
        self.verboseprint("Checking mode to use `set_control_type`")
        # self.check_mode(0)

        #Set the control type
        self.send_message(message_builder('3f',  int_to_hex(control_type)), write=True)
        self.verboseprint('Control type set to: {}'.format(control_type))

    #---------------------------------------------------------------------------
    #    Set functions for Normal set mode
    #    These functions are used to set and hold a single temperature
    #    or output level.
    #---------------------------------------------------------------------------

    def set_temp(self, temperature):
        """
        Set the temperature and hold that temperature.
        Input:
        `temperature`(int): Temperature in degree Celsius

        Only works in the Normal set mode: set_mode(0) and
        control type PID: set_control(0)
        """
        #Check mode
        self.check_mode(0)
        
        #Set the temperature
        temperature = int(temperature * 100)
        self.send_message(message_builder('1c',  int_to_hex(temperature)), write=True)
        self.verboseprint('Temperature set to: {}C'.format(temperature/100))

    def set_output(self, output):
        """
        Set the output to a specific value.
        Input:
        `output`(int): range -511 to 511 for -100% to 100% output.

        Only works in the Normal set mode: set_mode(0) and control
        type Manual: set_control(1)
        """
        #Check mode
        self.check_mode(0)

        self.send_message(message_builder('40',  int_to_hex(output)), write=True)
        self.verboseprint('Output set to: {}'.format(output))

    #---------------------------------------------------------------------------
    #    Set functions for ramp/soak mode
    #    Functions to set the ramp/soak sequence.
    #---------------------------------------------------------------------------

    def set_soak_temp(self, location, temperature):
        """
        Set the soak temperature (holding temperature) of the specified location.
        Input:
        `location`(int): locations 1-8
        `temperature`(float, max 2 decimals): Temperature in degree centigrade.
            Positive and negative values are possible.
        
        """
        self.validate_data(location)
        #Check mode
        self.check_mode(1)
        
        location_code = 'a' + str(location-1)
        temperature = int(temperature * 100)
        #If the temperature is negative use the "two's complement"
        if temperature < 0:
            temperature = 2**16 + temperature
        
        #Set soak temperature
        self.send_message(message_builder(location_code, int_to_hex(temperature)), write=True)

    def set_ramp_time(self, location, time):
        """
        Set the ramp time to specified time. The temperature control unit will 
        ramp to the new temperature in the given time.
        Input:
        `location`(int): locations 1-8.
        `time`(int): Number of seconds that the ramp should take. 
        
        """
        #Check input
        self.validate_data(location)
        #Check mode
        self.check_mode(1)
        
        #Set ramp time
        location_code = 'b' + str(location-1)
        self.send_message(message_builder(location_code, int_to_hex(time)), write=True)

    def set_soak_time(self, location, time):
        """
        Set the soak time, number of seconds the temperature should be kept at
        the soak temperature. 
        Input:
        `location`(int): Locations 1-8.
        `time`(int): Seconds the soak temperature should be kept.
        
        """
        #Check input
        self.validate_data(location)
        if type(time) != int or (1< time > 32768): #half 2**16
            raise ValueError('Invalid time: "{}", type: "{}. Must be a integer in the range 1-32768.'.format(location, type(location)))
        #Check mode
        self.check_mode(1)
            
        #set soak time
        location_code = 'c' + str(location-1)
        self.send_message(message_builder(location_code, int_to_hex(time)), write=True)

    def set_repeats(self, location, repeats):
        """
        Set the number of repeats to a temperature location. The program will 
        cycle over all 8 locations in sequence and counts how many times a 
        location is performed.
        Warning: There is some strange behavior if one of the locations has 
        fewer repeats than the other locations, it will be executed as many
        times as the location with the most. 
        Input:
        `location`(int): locations 1-8
        `Repeats`(int): Number of times the temperature sequence should be 
            repeated (i.e., 
            repeats == 2 will perform the action the first time, plus 
            2 repeats for a total of 3 times). 
        
        """
        #Check input
        self.validate_data(location)
        #Check mode
        self.check_mode(1)
        
        location_code = 'd' + str(location-1)
        self.send_message(message_builder(location_code, int_to_hex(repeats)), write=True)

    def set_repeat_location(self, location, repeat_loc):
        """
        Set which location has to be performed after the specified location is
        done.
        Input:
        `location`(int): locations 1-8
        `repeat_loc`(int): locations 1-8
        
        """
        #Check input
        self.validate_data(location)
        self.validate_data(repeat_loc)
        #Check mode
        self.check_mode(1)
        
        location_code = 'e' + str(location-1)
        self.send_message(message_builder(location_code, int_to_hex(repeat_loc)), write=True)

    #==========================================================================
    #    Ramp/soak mode PID control
    #==========================================================================

    def get_proportional_bandwidth(self):
        """Get the proportional bandwidth (in °C)."""
        self.send_message(message_builder('51'))  # Command for reading proportional bandwidth
        return response_to_int(self.read_message()) / 100  # Convert from hex and scale
    
    def get_integral_gain(self):
        """Get the integral gain (in repeats/minute)."""
        self.send_message(message_builder('52'))  # Command for reading integral gain
        return response_to_int(self.read_message()) / 100  # Convert and scale appropriately
    
    def get_derivative_gain(self):
        """Get the derivative gain (in minutes)."""
        self.send_message(message_builder('53'))  # Command for reading derivative gain
        return response_to_int(self.read_message()) / 100  # Convert and scale
    
    def set_proportional_bandwidth(self, bandwidth):
        """Set the proportional bandwidth (in °C)."""
        value = int(bandwidth * 100)  # Multiply by 100 and convert to int
        hex_value = int_to_hex(value)  # Convert to hex
        self.send_message(message_builder('1d', hex_value))  # Send message
    
    def set_integral_gain(self, gain):
        """Set the integral gain (in repeats/minute)."""
        value = int(gain * 100)
        hex_value = int_to_hex(value)
        self.send_message(message_builder('1e', hex_value))
    
    def set_derivative_gain(self, gain):
        """Set the derivative gain (in minutes)."""
        value = int(gain * 100)
        hex_value = int_to_hex(value)
        self.send_message(message_builder('1f', hex_value))
    
    def get_location_proportional(self, location):
        """Retrieve the proportional bandwidth for a specific ramp/soak location."""
        # Step 1: Set the index with command 82 (using write mode to acknowledge index setting)
        self.send_message(message_builder('82', int_to_hex(location)), write=True)
        # Step 2: Read the proportional bandwidth with command 84 (handled as a special command)
        response = self.send_message(message_builder('84', int_to_hex(location)))
        # Process and return the response value
        print(f"Proportional Value Response: {response}")
        return response_to_int(response) / 100    

    def _get_location_proportional_raw(controller, location):
        """Directly communicate with the controller to get the proportional bandwidth."""
        # Step 1: Set the index for the location with command 82
        set_index_message = message_builder('82', controller.int_to_hex(location))
        print(f"Setting index with message: {''.join(set_index_message)}")
        controller.ser.write(''.join(set_index_message).encode('utf-8'))
        index_response = controller.ser.read(10)
        print(f"Index set response: {index_response}")
        # Step 2: Send the read command with index using command 84
        read_message = controller.message_builder('84', controller.int_to_hex(location))
        print(f"Reading proportional value with message: {''.join(read_message)}")
        controller.ser.write(''.join(read_message).encode('utf-8'))
        read_response = controller.ser.read(10)
        print(f"Proportional value read response: {read_response}")
        # Interpret the response
        return controller.response_to_int(read_response) / 100

    def get_location_integral(self, location):
        """Retrieve the integral gain for a specific ramp/soak location."""
        # Step 1: Set the index with command 85 (using write mode to acknowledge index setting)
        self.send_message(message_builder('85', int_to_hex(location)), write=True)
        # Step 2: Read the integral gain with command 87 (handled as a special command)
        response = self.send_message(message_builder('87', int_to_hex(location)))
        # Process and return the response value
        #print(f"Integral Gain Response: {response}")
        return response_to_int(response) / 100

    def get_location_derivative(self, location):
        """Retrieve the derivative gain for a specific ramp/soak location."""
        # Step 1: Set the index with command 88 (using write mode to acknowledge index setting)
        self.send_message(message_builder('88', int_to_hex(location)), write=True)
        # Step 2: Read the derivative gain with command 8a (handled as a special command)
        response = self.send_message(message_builder('8a', int_to_hex(location)))
        # Process and return the response value
        #print(f"Derivative Gain Response: {response}")
        return response_to_int(response) / 100

    def clear_sequence(self):
        """
        Clear all ramp/soak steps by zeroing ramp time, soak time, repeats, and GoTo.
        As an extra caution, it also sets the soak temperature to the default temperature.
        Optionally resets PID gains for all steps.
        """
        if self.get_mode() != 1:
            self.set_mode(1)

        for loc in range(1, 9):
            self.set_single_sequence(
                location=loc,
                temp=self.default_temp,
                ramp_time=0,
                soak_time=0,
                repeats=0,
                go_to=None
            )
            # Optional: reset PID gains (or use sensible defaults)
            self.set_location_proportional(loc, bandwidth=1.0)
            self.set_location_integral(loc, gain=0.0)
            self.set_location_derivative(loc, gain=0.0)

    def set_location_proportional(self, location, bandwidth):
        """Set the proportional bandwidth for a specific ramp/soak location."""
        # Set the index for the location (use command 82)
        self.send_message(message_builder('82', int_to_hex(location)), write = True)
        # Now write the proportional value at the specified index (use command 83)
        hex_value = int_to_hex(int(bandwidth * 100))
        self.send_message(message_builder('83', hex_value), write=True)

    def set_location_integral(self, location, gain):
        """Set the integral gain for a specific ramp/soak location."""
        # Set the index for the location (use command 85)
        self.send_message(message_builder('85', int_to_hex(location)))
        # Now write the integral value at the specified index (use command 86)
        hex_value = int_to_hex(int(gain * 100))
        self.send_message(message_builder('86', hex_value), write=True)

    def set_location_derivative(self, location, gain):
        """Set the derivative gain for a specific ramp/soak location."""
        # Set the index for the location (use command 88)
        self.send_message(message_builder('88', int_to_hex(location)))
        # Now write the derivative value at the specified index (use command 89)
        hex_value = int_to_hex(int(gain * 100))
        self.send_message(message_builder('89', hex_value), write=True)
    
    def set_timer_run_method(self, method):
        """
        Set the ramp/soak timer run method.
        Args:
            method (int): Timer run method. 
                        0 = Set Temp Only, 1 = Wait for control temp.
        """
        if method not in [0, 1]:
            raise ValueError("Invalid method. Must be 0 (Set Temp Only) or 1 (Wait for control temp).")
        hex_value = int_to_hex(method)
        self.send_message(message_builder('f0', hex_value), write=True)
        available_methods = ["Set Temp Only", "Wait for control temp"]
        print(f"Timer Run Method set to method {method}: {available_methods[method]}")

    def get_timer_run_method(self):
        """
        Retrieve the current ramp/soak timer run method.
        Returns:
            int: Current timer run method (0 = Set Temp Only, 1 = Wait for control temp).
        """
        response = self.send_message(message_builder('f1'))
        return response_to_int(response)

    #--------------------------------------------------------------------------
    #    Start stop functions
    #--------------------------------------------------------------------------

    def start_soak(self):
        """
        Start the ramp/soak temperature control and execute all sequences
        in the locations.

        """
        #Check mode
        self.check_mode(1)
        #Start soak
        self.send_message(message_builder('08', '0001'))

    def idle_soak(self):
        """
        Stop the ramp/soak execution.        
        NOTE: The controller automatically forces the output% to 0% when a program has (a) completed or (b)
        has been exited before completion, regardless of the OUTPUT ENABLE setting. 
        """
        #Check mode
        self.check_mode(1)
        #Set to idle
        self.send_message(message_builder('08', '0000'))

    def output_enable(self, enable):
        """
        Enable or disable the output.
        Args:
            enable (bool): True to enable the output, False to disable.
        NOTE: The controller automatically forces the output% to 0% when a program has (a) completed or (b)
        has been exited before completion, regardless of the OUTPUT ENABLE setting. 
        """
        if not isinstance(enable, bool):
            raise ValueError("Enable must be a boolean value (True or False).")
        
        value = 1 if enable else 0
        hex_value = int_to_hex(value)  # Convert to hex
        self.send_message(message_builder('30', hex_value), write=True)
        print(f"Output {'enabled' if enable else 'disabled'} successfully.")

    def is_output_enabled(self):
        """
        Check if the output is enabled.
        Returns:
            bool: True if output is enabled, False otherwise.
        """
        response = self.send_message(message_builder('64'))
        if response is None:
            raise RuntimeError("Failed to retrieve output status from the controller.")
        
        status = response_to_int(response)
        if status not in [0, 1]:
            raise ValueError(f"Unexpected output status value: {status}")
        
        print(f"Output Status: {'Enabled' if status == 1 else 'Disabled'}")
        return status == 1

    def set_idle(self):
        """
        Set the device to output control mode with 0 output.
        This method sets the device to idle mode by setting the mode to 0 and the output to 0.
        Note that using set_idle() changes the control type to 1. To wake up from idle mode and 
        be able to get any output other than 0, you need to set the control type back to 0 by calling `set_control_type(1)`).

        """
        self.set_mode(0)
        self.set_output(0)
        self.set_control_type(1)

    def set_active(self):
        '''
        Sets the TC720 device to active control mode.

        This method checks the current control type of the TC720 device. If the device is in idle mode, that is, manual control type 1,
        it switches the device to active mode (control type 0). This is the counterpart of the `set_idle` method, which
        sets the device to idle mode.

        Methods:
        - get_control_type(): Retrieves the current control type of the device.
        - set_control_type(type): Sets the control type of the device.
        - verboseprint(message): Prints a verbose message if verbose mode is enabled.
        '''
        if self.get_control_type() == 1:
            self.verboseprint("Setting TC720 to control type 0 (active)")
            self.set_control_type(0)

    #==========================================================================
    #    Combined functions
    #    These are the most useful to the user
    #==========================================================================

    def get_ramp_soak_delta(self):
        """
        Retrieve the allowable delta for the ramp/soak timer run method.
        Returns:
            float: Fixed temperature difference in degrees (1.00 to 20.00).
        """
        # Send the read command (f3)
        response = self.send_message(message_builder('f3'))
        # Convert response to float (hex to decimal, then divide by 100)
        delta = response_to_int(response) / 100
        return delta

    def set_ramp_soak_delta(self, delta):
        """
        Set the allowable delta for the ramp/soak timer run method.
        Args:
            delta (float): Fixed temperature difference in degrees (0.1 to 20.00).
        """
        if not (0.1 <= delta <= 20.00):
            raise ValueError(f"Invalid delta: {delta}. Must be between 0.1 and 20.00.")

        # Convert delta to hexadecimal (multiply by 100, then convert to hex)
        hex_value = int_to_hex(int(delta * 100))
        # Send the write command (f2) with the hex value
        self.send_message(message_builder('f2', hex_value), write=True)
        self.verboseprint(f"Ramp Soak Temperature Delta set to: {delta}")

    def get_loaded_program(self, location='all'):
        """
        Retrieve the current loaded program from the controller, including PID values for each step.
        Input:
            `location` (list, int, or str): Specify one location as an integer (1-8),
                multiple locations as a list of integers, or "all" to retrieve data
                from all locations (default is "all").
        Returns:
            dict: A dictionary where keys are step locations and values are dictionaries
                with parameters for each step:
                {
                    1: {'Temp': 22.0, 'Ramp Time': 30, 'Soak Time': 300,
                        'Repeats': 2, 'Repeat Location': 2, 'P': 22.0, 'I': 1.0, 'D': 0.0},
                    ...
                }
        """
        # Prepare the list of locations to retrieve
        if location == 'all':
            location = list(range(1, 9))  # Locations 1-8
        elif not isinstance(location, list):
            location = [location]

        # Initialize the dictionary for the loaded program
        loaded_program = {}

        for loc in location:
            print(f"Retrieving step {loc}...")  # Progress print to prevent freeze perception
            loaded_program[loc] = {
                'Temp': self.get_soak_temp(loc),
                'Ramp Time': self.get_ramp_time(loc),
                'Soak Time': self.get_soak_time(loc),
                'Repeats': self.get_repeats(loc),
                'Repeat Location': self.get_repeat_location(loc),
                'P': self.get_location_proportional(loc),
                'I': self.get_location_integral(loc),
                'D': self.get_location_derivative(loc),
            }

        print("Loaded program retrieval complete.")
        return loaded_program


    def get_sequence(self, location='all'):
        """
        Get the current sequence of the temperature control unit. There are 8 
        locations where the different parameters that define the ramp and soak
        are specified. This function repeats a single row or the full table. 
        Input:
        `location`(list, int or str): Specify one location as an integer (1-8).
            Or specify multiple locations as a list of integers. Or use the 
            keyword "all" to retrieve data of all locations (takes 4-5 seconds)
        Returns:
        Array of the data. The first row contains the headers of the table:
        ['Loc', 'Temp', 'Ramp time', 'Soak time', 'Repeats', 'Repeat loc']
        'Loc': Location the data is coming from.
        'Temp': The soak temperature, which is the target temperature.
        'Ramp time': The time the ramp takes to reach the soak temperature.
        'Soak time' : The time the soak temperature should be kept.
        'Repeats': The number of times the step (location) should be repeated.
        'Repeat loc': The next step in the sequence. 
        The subsequent rows contain the data of the different locations. 
        
        """
        #Initiate the array with the headers
        seq = np.array([['Loc', 'Temp', 'Ramp time', 'Soak time', 'Repeats', 'Repeat loc']])
        
        #Make the list of locations to retrieve
        if location == 'all':
            location = [1,2,3,4,5,6,7,8]
        elif type(location) != list:
            location = [location]
         
        #Add the data to the array
        for i in location:
            seq = np.append(seq, [[i, self.get_soak_temp(i), self.get_ramp_time(i), self.get_soak_time(i), self.get_repeats(i), self.get_repeat_location(i)]], axis=0)    
        
        return seq

    def set_single_sequence(self, location, temp=20, ramp_time=60, 
                            soak_time=30000, repeats=1, go_to=None):
        """
        Set the ramp and temperature settings of one location. 
        Input:
        `location`(int): Location to alter (1-8).
        `temp`(float, max 2 decimals): Target temperature in Celsius.
        `ramp_time`(int): Time it has to take to ramp up to the target 
            temperature.
        `soak_time`(int): Time the temperature has to be kept at the target
            temperature. In seconds, max = 30000 seconds. 
            Actually it should be 32767, which is 0.5 * 2**16, but higher
            values gives checksum errors sometimes.
        `repeats`(int): Number of times the location has to be repeated. The
            program will cycle over all 8 locations in sequence and counts how 
            many times a location is performed. 
            Warning: There is some strange behavior if one of the locations 
            has fewer repeats than the other locations, it will be executed 
            as many times as the location with the most. 
        `go_to`(int, None): If specified indicates the next location to
            execute. If set to "None" it will default to the next location. 
            If the location = 8, it will go to location 1. 
        
        """
        # Check input
        self.validate_data(location)

        self.set_soak_temp(location, temp)
        self.set_ramp_time(location, ramp_time)
        self.set_soak_time(location, soak_time)
        self.set_repeats(location, repeats)

        if go_to is None:
            # Default to the next location in sequence (wrap around to 1 after 8)
            next_loc = (location % 8) + 1
        elif isinstance(go_to, int) and 1 <= go_to <= 8:
            # Use the specified `go_to` value
            next_loc = go_to
        else:
            raise ValueError(f'Invalid go_to: "{go_to}", type: "{type(go_to)}". '
                         'Must be an integer in the range 1-8.')
        self.set_repeat_location(location, next_loc)
     
    #==========================================================================
    #   Wait until desired temperature is reached
    #==========================================================================

    def waitTemp(self, target_temp, error=1, array_size=5, sd=0.01, 
                timeout_min = 5, set_idle = True):
        """
        Wait until the target temperature has been reached. This can also be
        done by waiting the ramp time, but use this function if you want to be
        sure it reached the temperature.
        Input:
        `tarselfget_temp`(float): Temperature to reach in Celsius.
        `error`(float): Degree Celsius error allowed between target and real 
            temperature.
        `array_size`(int): Size of array to check if stable temperature plateau 
            is reached. Default = 5
        `sd`(float): Standard deviation, if sd of temperature array drops below 
            threshold value, the temperature has been reached and is stable.
            Default = 0.01
        `timeout_min`(float): Number of minutes after which the program times-out.
            It will raise and exception if the temperature could not be 
            reached withing the timeout period if "set_idle" is "True", 
            otherwise it will only raise an Warning.
        `set_idle`(bool): If True it will set the controller to idle if the 
            target temperature could not be reached within the timeout period.
            Otherwise it will be able to continue provided that there are no
            errors on the controller.
            
        """
        bufferT = deque(maxlen=array_size)
        counter = 0
        timeout_seconds = timeout_min * 60

        while True:
            tic = time.time()

            cur_temp = self.get_temp()
            bufferT.append(cur_temp)
            
            self.verboseprint('Current temperature: ', cur_temp, ' Standard deviation: ', round(np.std(bufferT), 3))

            # Check if temp is within the error range of the target_temp
            if (target_temp-error) < cur_temp < (target_temp+error):
                self.verboseprint('Within range of target temperature {}C with error {}C'.format( target_temp, error))
                if counter > array_size:
                    #Check if slope has plateaus by checking the standard deviation
                    if np.std(bufferT) < sd:
                        self.verboseprint('Temperature stable, slope minimal')
                        break
            if counter >= (timeout_seconds): #Raise and exception after the timeout period
                #Make sure there are no errors on the system
                self.check_error(set_idle=set_idle, raise_exception=True)
            
                if set_idle:
                    self.set_idle()
                    raise Exception('Temperature could not be reached in {} minutes, check {} system.'.format(timeout_min, self.name))
                else:
                    warnings.warn('Temperature could not be reached in {} minutes, check {} system.'.format(timeout_min, self.name))
                    break


            counter +=1        
            toc = time.time()
            execute_time = toc - tic
            if execute_time > 1:
                execute_time = 0.001
            # Check every second
            time.sleep(1-execute_time)


    #==========================================================================
    #    Check errors
    #==========================================================================

    def check_error(self, set_idle = True, raise_exception = True):
        """
        Check if there are errors on the system.  
        Input:
        `set_idle`(bool): If an error is detected the function will set the
            temperature controller to idle.
        `raise_exception`(bool): If and error is detected and "raise_exception"
            is set to "True", it will raise an exception and thereby 
            terminate the running program. If set to "False" it will throw a 
            warning only and the program can continue. Do this with caution!
            Useful if another program does the error handling.
        Returns:
        If there are no errors it will return a list with True and a message.
        If there is an error detected it will raise and exception or return a
        list with False and the error message if "rais_exception" is set to
        "False". This can then be interpreted by another program.
        
        """
        #Ask for error
        self.send_message(message_builder('03'))
        response = self.read_message()
        response = '{b:0>6}'.format(b = bin(int(response[1:5], 16))[2:])
          
        #No errors detected
        if response == '000000':
            self.verboseprint('No errors on temperature controller: {}'.format(self.name))
            return [True, 'No errors on temperature controller: {}'.format(self.name)]
        
        #Error detected
        else:
            reset='Device NOT set to idle'
            #Try to set the controller to idle
            if set_idle:
                self.set_idle()
                reset = 'Device is set to idle.'
                self.verboseprint(reset)
            
            #Report the error
            error_list = ['Over Current Detected', 'Key press to store value',
                          'Low Input Voltage', 'Open Input 2', 'Open Input 1', 
                          'Low Alarm 2', 'High Alarm 2', 'Low Alarm 1', 
                          'High Alarm 1',]
            current_errors = [error_list[n] for n,i in enumerate(response) if i == '1']
            #Check if it should raise an exception or give a warning.
            if raise_exception:
                raise Exception('Error(s) on {}: {}. {}'.format(self.name, current_errors, reset))
            else:
                warnings.warn('Error(s) on {}: {}. {}'.format(self.name, current_errors, reset))
                return [False, 'Error(s) on {}: {}. {}'.format(self.name, current_errors, reset)]

#!/usr/bin/python
"""
Copyright Mikhail Doronin: original code taken from px100.py
Copyright Constantin Wenger: modified for DL24M
licensed as GPLv3
"""

from datetime import time
from math import modf
from numbers import Number
from time import sleep
from numpy import byte

import pyvisa as visa

from instruments.instrument import Instrument


class DL24M(Instrument):

    ISON = 0x10
    VOLTAGE = 0x11
    CURRENT = 0x12
    TIME = 0x13
    CAP_AH = 0x14
    CAP_WH = 0x15
    TEMP = 0x16
    LIM_CURR = 0x17
    LIM_VOLT = 0x18
    TIMER = 0x19
    # codes 20-22 are queryed by official app unknown reason
    CLEARDATA = 0x20

    OUTPUT_ON = 0x01
    SETCURR = 0x02 # or power or what ever other mode, power is 1/10 watts
    SETVCUT = 0x03
    SETTMR = 0x04
    RESETCNT = 0x05
    SETMODE = 0x06 # with values 0x00 0x00=CC CV=0x00 0x01 CR=0x00 0x02 CP=0x00 0x03
    UNKNOW = 0x07  # on stop it sends 0x01 0x00 0x00 and 0x07 0x00 0x001

    ENABLED = 0x0100
    DISABLED = 0x0000

    MUL = {
        ISON: 1,
        VOLTAGE: 1000.,
        CURRENT: 1000.,
        CAP_AH: 1000.,
        CAP_WH: 1000.,
        TEMP: 1,
        LIM_CURR: 100.,
        LIM_VOLT: 100.,
    }

    KEY_CMDS = {
        'is_on': ISON,
        'voltage': VOLTAGE,
        'current': CURRENT,
        'time': TIME,
        'cap_ah': CAP_AH,
        'cap_wh': CAP_WH,
        'temp': TEMP,
        'set_current': LIM_CURR,
        'set_voltage': LIM_VOLT,
        'set_timer': TIMER,
    }

    FREQ_VALS = [
        'is_on',
        'voltage',
        'current',
        'time',
        'cap_ah',
    ]

    AUX_VALS = [
        'cap_wh',
        'temp',
        'set_current',
        'set_voltage',
        'set_timer',
    ]

    COMMANDS = {
        Instrument.COMMAND_ENABLE: OUTPUT_ON,
        Instrument.COMMAND_SET_VOLTAGE: SETVCUT,
        Instrument.COMMAND_SET_CURRENT: SETCURR,
        Instrument.COMMAND_SET_TIMER: SETTMR,
        Instrument.COMMAND_RESET: RESETCNT,
    }

    VERIFY_CMD = {
        Instrument.COMMAND_ENABLE: 'is_on',
        Instrument.COMMAND_SET_VOLTAGE: 'set_voltage',
        Instrument.COMMAND_SET_CURRENT: 'set_current',
        Instrument.COMMAND_SET_TIMER: 'set_timer',
        Instrument.COMMAND_RESET: 'cap_ah',
    }

    def __init__(self, device):
        print(device)
        self.device = device
        self.name = "DL24M"
        self.aux_index = 0
        self.data = {
            'is_on': 0.,
            'voltage': 0.,
            'current': 0.,
            'time': time(0),
            'cap_ah': 0.,
            'cap_wh': 0.,
            'temp': 0,
            'set_current': 0.,
            'set_voltage': 0.,
            'set_timer': time(0),
        }

    def probe(self):
        print("probe")
        if not isinstance(self.device, visa.resources.SerialInstrument):
            return False

        self.port = self.device.resource_name.split('::')[0].replace('ASRL', '')
        self.__setup_device()
        self.__clear_device()

        return self.__is_number(self.getVal(DL24M.VOLTAGE))

    def readAll(self, read_all_aux=False):
        print("readAll")
        self.__clear_device()
        self.update_vals(DL24M.FREQ_VALS)

        if read_all_aux:
            self.update_vals(DL24M.AUX_VALS)
        else:
            self.update_val(DL24M.AUX_VALS[self.__next_aux()])

        return self.data

    def update_vals(self, keys):
        for key in keys:
            self.update_val(key)

    def update_val(self, key):
        value = self.getVal(DL24M.KEY_CMDS[key])
        if (value is not False):
            self.data[key] = value

    def command(self, command, value):
        if command not in (DL24M.COMMANDS.keys()):
            return False

        for i in range(0, 3):
            self.setVal(DL24M.COMMANDS[command], value)
            sleep(0.5)
            self.update_val(DL24M.VERIFY_CMD[command])
            if self.data[DL24M.VERIFY_CMD[command]] == value:
                break
            print("retry " + command)
            print(self.data[DL24M.VERIFY_CMD[command]])
            print(value)
            sleep(0.7)

        if (command == Instrument.COMMAND_RESET):
            self.update_vals(DL24M.AUX_VALS)

    def getVal(self, command):
        ret = self.writeFunction(command, [0, 0])
        if (not ret or len(ret) == 0):
            print("no answer")
            return False
        elif (len(ret) == 1 and ret[0] == 0x6F):
            print("setval")
            return False
        elif (len(ret) < 8 or ret[0] != 0xCA or ret[1] != 0xCB
              or ret[6] != 0xCE or ret[7] != 0xCF or ret[2] != command):
            print("Receive error")
            return False

        try:
            mult = DL24M.MUL[command]
        except:
            mult = 1000.

        if (command == DL24M.TIME or command == DL24M.TIMER):
            hh = ret[3]
            mm = ret[4]
            ss = ret[5]
            return time(hh, mm, ss)  #'{:02d}:{:02d}:{:02d}'.format(hh, mm, ss)
        else:
            print(ret)
            print(command, bytes(ret).hex("-"))
            return int.from_bytes(ret[3:6], byteorder='big') / mult

    def setVal(self, command, value):
        if isinstance(value, float):
            f, i = modf(value)
            value = [int(i), round(f * 100)]
        elif isinstance(value, time):
            value = (value.second + value.minute * 60 +
                     value.hour * 3600).to_bytes(2, byteorder='big')
        elif (command == DL24M.OUTPUT_ON and value):
            value = [0x01, 0x00]
        else:
            value = value.to_bytes(2, byteorder='big')
        ret = self.writeFunction(command, value)
        return ret == None

    def writeFunction(self, command, value):
        if command >= 0x10:
            resp_len = 8
        else:
            resp_len = 0

        frame = bytearray([0xB1, 0xB2, command, *value, 0xB6])
        try:
            self.device.write_raw(frame)
            if resp_len == 0:
                return None
            bytes_read = self.device.read_bytes(resp_len)
            if (bytes_read[0] != 0xCA or bytes_read[1] != 0xCB):  # this is a var length status message, skip to CA, CB?
                # see if we read 0xCA already
                try:
                    idx = bytes_read.index(0xCA)
                    if (idx+1 < resp_len):
                        # we are at the start of the frame
                        if (bytes_read[idx+1] == 0xCB):
                            response = bytes_read[idx:]
                            bytes_left = resp_len - len(response)
                            response += self.device.read_bytes(bytes_left)
                            bytes_read = response
                        else:
                            bytee = bytes([0x00,])
                            while (len(bytee) != 2 or bytee[0] != 0xCA or bytee[1] != 0xCB):
                                if (len(bytee) == 2): # if we get here we got first byte right but 2nd wrong
                                    bytee = bytes([bytee[1], 0x00])
                                while(bytee[0] != 0xCA):
                                    bytee = self.device.read_bytes(1)
                                bytee += self.device.read_bytes(1)
                            bytes_read = bytee + self.device.read_bytes(6)
                    else: # there is no further byte to probe
                        bytee = bytes([bytes_read[idx]])
                        while (len(bytee) != 2 or bytee[0] != 0xCA or bytee[1] != 0xCB):
                            if (len(bytee) == 2): # if we get here we got first byte right but 2nd wrong
                                bytee = bytes([bytee[1], 0x00])
                            while(bytee[0] != 0xCA):
                                bytee = self.device.read_bytes(1)
                            bytee += self.device.read_bytes(1)
                        bytes_read = bytee + self.device.read_bytes(6)
                except ValueError:
                    # we do not have the start yet
                    bytee = bytes([0x00,])
                    while (len(bytee) != 2 or bytee[0] != 0xCA or bytee[1] != 0xCB):
                        if (len(bytee) == 2): # if we get here we got first byte right but 2nd wrong
                            bytee = bytes([bytee[1], 0x00])
                        while(bytee[0] != 0xCA):
                            bytee = self.device.read_bytes(1)
                        bytee += self.device.read_bytes(1)
                    bytes_read = bytee + self.device.read_bytes(6)
            return bytes_read
        except Exception as inst:
            print(type(inst))    # the exception instance
            print(inst.args)     # arguments stored in .args
            print(inst)
            print("error reading bytes")
            return False

    def turnOFF(self):
        print("turnoff")
        self.setVal(DL24M.OUTPUT_ON, DL24M.DISABLED)

    def close(self):
        self.turnOFF()
        sleep(.2)
        self.device.close()

    def __setup_device(self):
        try:
            self.device.timeout = 500
            self.device.baud_rate = 9600
            self.device.data_bits = 8
            self.device.stop_bits = visa.constants.StopBits.one
            self.device.parity = visa.constants.Parity.none
            self.device.flow_control = visa.constants.ControlFlow.none
        except  e:
            print(e)
            pass

    def __clear_device(self):
        try:
            self.device.read_bytes(self.device.bytes_in_buffer)
        except Exception as inst:
            print(type(inst))    # the exception instance
            print(inst.args)     # arguments stored in .args
            print(inst)
            print("error reading bytes")
            self.device.close
            return False

    def __next_aux(self):
        self.aux_index += 1
        if self.aux_index >= len(DL24M.AUX_VALS):
            self.aux_index = 0
        return self.aux_index

    def __is_number(self, value):
        return isinstance(value, Number) and not isinstance(value, bool)

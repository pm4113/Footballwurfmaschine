from pdb import set_trace as bp 
import CModule
import Queue
import serial
import threading
import time 
from datetime import datetime
import argparse


__author__ = 'kentindell'


"""
Microcontroller Interconnect Network (MIN) version 1.0
Python reference implementation and example program
Copyright (c) 2014-2015 JK Energy Ltd.
Licensed under MIT License.
"""

debug = True

global uart_status
uart_status = 0
controller = 0


#print "Start: %s" % datetime.now()     # get time in ms
#time.sleep(0.0001)
#print "Stop: %s" % datetime.now()


class Frame:
    """
    Class to handle MIN 1.0 frame handling. Constructed after receiving frame data from the serial port and
    also in prelude to sending on the serial port.
    """

    HEADER_BYTE = 0xaa
    STUFF_BYTE = 0x55
    EOF_BYTE = 0x55

    def checksum(self):
        """
        Compute Fletcher's checksum (16-bit version)
        sum1 and sum2 are 16 bit integers so must be clipped back to this range
        Return a list of high byte then low byte (big-endian order on the wire)
        """
        sum1 = 0xff
        sum2 = 0xff

        checksummed_data = [self.frame_id, self.get_control()] + self.payload

        for b in checksummed_data:
            sum1 += b
            sum1 &= 0xffff  # Results wrapped at 16 bits
            sum2 += sum1
            sum2 &= 0xffff
            sum1 = (sum1 & 0x00ff) + (sum1 >> 8)
            sum2 = (sum2 & 0x00ff) + (sum2 >> 8)
            
#        checksum = ((sum2 << 8) & 0xffff) | sum1
        checksum = ((sum2 & 0x00ff) << 8) | (sum1 & 0x00ff)
        high_byte = (checksum & 0xff00) >> 8
        low_byte = checksum & 0x00ff
        print high_byte
        print low_byte
        return [high_byte, low_byte]

    def __init__(self, serial_handler, frame_id=0, payload=list()):
        """
        id is the MIN frame id
        payload is a list of up to 15 bytes that is the payload of the frame
        """
        self.frame_id = frame_id
        self.payload = payload
        self.stuffed = None
        self.handler = serial_handler
        if len(self.payload) > 15:
            raise Exception("Payload too big")

    def transmit(self):
        """
        Transmit self through the assigned serial handler
        """
        self.handler.send_queue.put(self.get_bytes())

    def __str__(self):
        s = "ID: 0x{0:02x}\n".format(self.frame_id)
        s += "Payload: {0}\n".format(':'.join('{:02x}'.format(i) for i in self.payload))

        return s

    def get_control(self):
        """
        Get the control byte based on the frame properties
        NB: In MIN 1.0 the top four bits must be set to zero (reserved for future)
        """
        tmp = 0
        tmp |= len(self.payload)

        return tmp

    def get_payload(self):
        return self.payload

    def get_bytes(self):
        """
        Get the on-wire byte sequence for the frame, including stuff bytes after every 0xaa 0xaa pair
        """
        raw = [self.frame_id] + [self.get_control()] + self.payload + self.checksum()
        self.stuffed = [self.HEADER_BYTE, self.HEADER_BYTE, self.HEADER_BYTE]

        count = 0

        for i in raw:
            self.stuffed.append(i)
            if i == self.HEADER_BYTE:
                count += 1
                if count == 2:
                    self.stuffed.append(self.STUFF_BYTE)
                    count = 0
            else:
                count = 0

        self.stuffed.append(self.EOF_BYTE)

        return self.stuffed

    def get_length(self):
        return len(self.payload)

    def get_id(self):
        return self.frame_id


class SerialHandler:
    """
    This class handles the serial port and sends frames to the port and receives them from the port.
    It creates two threads, one for writing and one for reading
    """

    # States for receiving a frame
    SOF, ID, CONTROL, PAYLOAD, CHECKSUM_HIGH, CHECKSUM_LOW, EOF = range(7)

    def __init__(self, received_frame_handler):
        self.header_bytes_seen = 0
        self.frame_id = 0
        self.frame_length = 0
        self.frame_payload = []
        self.frame_checksum_bytes = []
        self.payload_bytes_to_go = 0
        self.frame = None
        self.state = self.SOF
        self.received_frame_handler = received_frame_handler

        # Initialize receiver and sender threads
        self.send_queue = Queue.Queue()

        self.receive_thread = threading.Thread(target=self.receiver)
        self.send_thread = threading.Thread(target=self.sender)

        self.receive_thread.daemon = True
        self.send_thread.daemon = True 

        self.receive_thread.start()
        self.send_thread.start()


    def receiver(self):
        """
        Receive loop that takes a byte at a time from the serial port and creates a frame
        """
        break_read = 1

        while(break_read):
            # Read a byte from the serial line (blocking call)
            fail_data = "NODATA"
            data = CModule.UartReceive()
            if data != fail_data:         
                CModule.InterruptUartReadOn()
                break_read = 0
                read = 1
            else:
               self.build_received_frame(ord(data[0]))
    
        if read:
            read = 0
            data = bytearray(data)
            if debug:
                for i in data:
                    print(i)
            for i in data:
                self.build_received_frame(i) 
            break_read = 1


    def sender(self):
        """
        Feed the queue into the serial port (blocking on reading the queue and the sending)
        """
        while True:
            frame_data = self.send_queue.get()
            data = frame_data
            if debug:
                print("Data TX on wire: %s" % ':'.join('0x{:02x}'.format(i) for i in frame_data))
            data = tuple(data)
            CModule.UartSend(data)        

    def build_received_frame(self, byte):
        """
        Read bytes in sequence until a frame has been pulled in
        """
        if self.header_bytes_seen == 2:
            self.header_bytes_seen = 0
            if byte == Frame.HEADER_BYTE:
                # If three header bytes in a row, reset state machine and start reading a new frame
                if debug:
                    print("Header seen")
                self.state = SerialHandler.ID
                return
            # Two in a row: we should see a stuff byte
            if byte != Frame.STUFF_BYTE:
                # Something has gone wrong with the frame, discard and reset
                print("Framing error: Missing stuff byte")
                CModule.InterruptUartReadOff()
                self.state = SerialHandler.SOF
                return
            else:
                # A stuff byte, discard and carry on receiving on the next byte where we were
                if debug:
                    print("Stuff byte discarded")
                return

        if byte == Frame.HEADER_BYTE:
            self.header_bytes_seen += 1
        else:
            self.header_bytes_seen = 0

        if self.state == SerialHandler.ID:
            if debug:
                print("ID byte")
            self.frame_id = byte
            self.state = SerialHandler.CONTROL
        elif self.state == SerialHandler.CONTROL:
            if debug:
                print("control byte")
            self.frame_length = byte & 0x0f
            if debug:
                print("control byte %s [length=%d]"
                      % ('0b{:08b}'.format(byte),
                         self.frame_length))
            self.payload_bytes_to_go = self.frame_length
            self.frame_payload = []
            if self.payload_bytes_to_go > 0:
                self.state = SerialHandler.PAYLOAD
            else:
                self.state = SerialHandler.CHECKSUM_HIGH
        elif self.state == SerialHandler.PAYLOAD:
            if debug:
                print("payload byte")
            self.frame_payload.append(byte)
            self.payload_bytes_to_go -= 1
            if self.payload_bytes_to_go == 0:
                self.state = SerialHandler.CHECKSUM_HIGH
        elif self.state == SerialHandler.CHECKSUM_HIGH:
            if debug:
                print("checksum high")
            self.frame_checksum_bytes = [byte]
            self.state = SerialHandler.CHECKSUM_LOW
        elif self.state == SerialHandler.CHECKSUM_LOW:
            if debug:
                print("checksum low")
            self.frame_checksum_bytes.append(byte)
            # Construct the frame object
            self.frame = Frame(serial_handler=self,
                               frame_id=self.frame_id,
                               payload=self.frame_payload)
            checksum_bytes = self.frame.checksum()
            if checksum_bytes != self.frame_checksum_bytes:
                # Checksum failure, drop it and look for a new one
                print("FAILED CHECKSUM")
                self.state = SerialHandler.SOF
            else:
                self.state = SerialHandler.EOF
        elif self.state == SerialHandler.EOF:
            if byte == Frame.EOF_BYTE:
                if debug:
                    print("EOF, frame passed up")
                    print(self.frame)
                # Frame is well-formed,pass it up for handling
                self.received_frame_handler(frame=self.frame)

            self.state = SerialHandler.SOF
            if uart_status >=1:
                print "Uart start sequence:" + str(uart_status)


# Decoder MIN network order 16-bit and 32-bit words
def min_decode(data):
    if len(data) == 2:
        # 16-bit big-endian integer
        return (data[0] << 8) | (data[1])
    elif len(data) == 4:
        # 32-bit big-endian integer
        return (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | (data[3])


# Encode a 32-bit integer into MIN network order bytes
def min_encode_32(x):
    return [(x & 0xff000000) >> 24, (x & 0x00ff0000) >> 16, (x & 0x0000ff00) >> 8, (x & 0x000000ff)]


# Encode a 16-bit integer into MIN network order bytes
def min_encode_16(x):
    return [(x & 0x0000ff00) >> 8, (x & 0x000000ff)]


# Called when a MIN frame has been received successfully from the serial line
def received_frame(frame):
    global message_id
    global data
    message_id = frame.get_id()
    data = frame.get_payload()
    #hier kommen die Daten die richtig ankommen ausgegeben#
    if False:
        pass
    else:
        global uart_status
        uart_status = 1
        if message_id == 0x00:              # Error
            print("RX Error: " + ':'.join('{:02x}'.format(i) for i in data))
        elif message_id == 0x10:            # Status Message
            print("RX Status: " + ':'.join('{:02x}'.format(i) for i in data))
        elif message_id == 0x20:            # 
            print("RX Ready: " + ':'.join('{:02x}'.format(i) for i in data))
        elif message_id == 0x02:
            print("Ping received: " + ':'.join('{:02x}'.format(i) for i in data))


def get_uart_status():
    global uart_status
    uart_start = 0
    if uart_status == 1:
        uart_status = 0
        uart_start = 1 
    return uart_start


def get_uart_rec_data():
    global message_id
    global data
    return (message_id, data)
    

def min_uart_send(frame_id, payload):
    if debug:
        print("Send via UART") 
    controller = SerialHandler(received_frame_handler=received_frame )
    f = Frame(controller, frame_id, payload)
    f.transmit()


def init_controller():
    controller = SerialHandler(received_frame_handler=received_frame)
    

